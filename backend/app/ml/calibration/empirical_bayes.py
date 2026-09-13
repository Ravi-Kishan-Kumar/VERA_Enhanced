"""Product-level Empirical Bayes aggregation (PRD §11).

A product with one 5.0 review must not outrank a product with 500 reviews
averaging 4.6. Each product's quality-weighted mean is shrunk toward the global
mean in proportion to how noisy that mean is (normal–normal model).

Model, for product j with review scores y_ij and trust weights w_ij::

    m_j   = Σ w_ij y_ij / Σ w_ij                  (trust-weighted mean)
    n_eff = (Σ w_ij)² / Σ w_ij²                   (Kish effective sample size)
    σ²_j  = max(weighted var_j, 0.05)             (noise floor, PRD weakness #5)
            — conservative default variance when the product has one review
    s²_j  = σ²_j / n_eff                          (sampling variance of m_j)
    B_j   = s²_j / (s²_j + τ²)                    (shrinkage factor)
    θ̂_j   = (1 − B_j)·m_j + B_j·μ                  (EB estimate)
    sd_j  = sqrt(B_j · τ²)                        (posterior sd = uncertainty)

Prior (fitted across all products, method of moments)::

    μ  = mean of all review scores
    τ² = max(Var_j(m_j) − mean_j(s²_j), 0.01)     (between-product variance)

Corrections vs the PRD sketch (see DECISIONS.md): the PRD set τ² to the variance
of *individual review scores* (that is total variance, not between-product
variance), used τ² as σ² for single-review products, and reported an ad-hoc
``sqrt(σ²/n + B²τ²)`` instead of the posterior standard deviation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np

from app.ml.constants import EARBUD_ASPECTS, SCORE_MAX, SCORE_MIN

SIGMA_SQ_FLOOR: Final = 0.05
TAU_SQ_FLOOR: Final = 0.01
#: Below this many products the between-product variance is not estimable.
MIN_PRODUCTS_FOR_PRIOR: Final = 3
#: Weakly informative fallbacks: product means within ~±1 star, reviews within ~±0.7.
DEFAULT_TAU_SQ: Final = 0.25
DEFAULT_SIGMA_SQ: Final = 0.5

_SENTIMENT_TIE_ORDER: Final = ("negative", "positive", "neutral")


@dataclass(frozen=True)
class ReviewSignal:
    """The per-review quantities aggregation needs."""

    product_asin: str
    corrected_score: float
    quality_weight: float
    star_rating: float
    aspects: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EBPrior:
    global_mean: float
    tau_sq: float
    pooled_sigma_sq: float
    n_products: int


@dataclass(frozen=True)
class ProductAggregate:
    product_asin: str
    corrected_score: float
    uncertainty: float
    review_count: int
    trust_weighted_score: float
    star_average: float | None
    eb_shrinkage_factor: float
    aspect_summary: dict[str, Any]


@dataclass(frozen=True)
class _ProductStats:
    n: int
    weighted_mean: float
    weighted_var: float | None  # None when n == 1
    n_eff: float


def _product_stats(scores: Sequence[float], weights: Sequence[float]) -> _ProductStats:
    y = np.asarray(scores, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    if y.size == 0:
        raise ValueError("cannot aggregate a product with no reviews")
    if y.shape != w.shape:
        raise ValueError("scores and weights must have the same length")
    w = np.where(np.isfinite(w) & (w > 0), w, 0.0)
    if w.sum() <= 0:  # all weights unusable -> uniform
        w = np.ones_like(y)
    w = w / w.sum()

    mean = float(np.dot(w, y))
    n_eff = float(1.0 / np.sum(w**2))
    var: float | None = None
    if y.size > 1:
        denom = 1.0 - float(np.sum(w**2))  # unbiased reliability-weighted variance
        var = float(np.dot(w, (y - mean) ** 2) / denom) if denom > 1e-12 else 0.0
    return _ProductStats(n=int(y.size), weighted_mean=mean, weighted_var=var, n_eff=n_eff)


class EmpiricalBayesAggregator:
    """Fit a prior across products, then shrink each product's mean toward it."""

    def __init__(self) -> None:
        self.prior: EBPrior | None = None

    # ------------------------------------------------------------------
    def fit(self, grouped: Mapping[str, tuple[Sequence[float], Sequence[float]]]) -> EBPrior:
        """Estimate μ, τ² and the pooled within-product variance.

        Args:
            grouped: ``asin -> (corrected_scores, quality_weights)``.
        """
        if not grouped:
            raise ValueError("fit() needs at least one product")
        stats = {asin: _product_stats(*sw) for asin, sw in grouped.items()}
        all_scores = np.concatenate([np.asarray(s, dtype=np.float64) for s, _ in grouped.values()])

        multi = [s for s in stats.values() if s.weighted_var is not None]
        if multi:
            dof = np.array([s.n - 1 for s in multi], dtype=np.float64)
            variances = np.array([s.weighted_var for s in multi], dtype=np.float64)
            pooled = float(np.dot(dof, variances) / dof.sum())
        else:
            pooled = DEFAULT_SIGMA_SQ
        pooled = max(pooled, SIGMA_SQ_FLOOR)

        if len(stats) >= MIN_PRODUCTS_FOR_PRIOR:
            means = np.array([s.weighted_mean for s in stats.values()])
            sampling = np.array([self._sigma_sq(s, pooled) / s.n_eff for s in stats.values()])
            tau_sq = max(float(means.var(ddof=1) - sampling.mean()), TAU_SQ_FLOOR)
        else:
            tau_sq = DEFAULT_TAU_SQ

        self.prior = EBPrior(
            global_mean=float(all_scores.mean()),
            tau_sq=tau_sq,
            pooled_sigma_sq=pooled,
            n_products=len(stats),
        )
        return self.prior

    @staticmethod
    def _sigma_sq(stats: _ProductStats, pooled_sigma_sq: float) -> float:
        # A one-review product has no within-product variance estimate. The
        # observed pooled variance can be deceptively near zero when existing
        # multi-review products are unanimous, so using it here would allow an
        # isolated 5.0 to outrank a well-supported 4.6. Use the documented
        # weakly informative variance instead; observed variance takes over as
        # soon as a product has two reviews.
        raw = (
            stats.weighted_var
            if stats.weighted_var is not None
            else max(pooled_sigma_sq, DEFAULT_SIGMA_SQ)
        )
        return max(raw, SIGMA_SQ_FLOOR)

    # ------------------------------------------------------------------
    def aggregate_product(
        self,
        corrected_scores: Sequence[float],
        quality_weights: Sequence[float],
        aspect_sentiments: Sequence[Mapping[str, Any]],
        star_ratings: Sequence[float] | None = None,
        product_asin: str = "",
    ) -> ProductAggregate:
        """Compute the EB-shrunk aggregate for one product. Requires :meth:`fit` first."""
        if self.prior is None:
            raise RuntimeError("call fit() before aggregate_product()")
        prior = self.prior
        stats = _product_stats(corrected_scores, quality_weights)

        s_sq = self._sigma_sq(stats, prior.pooled_sigma_sq) / stats.n_eff
        shrink = float(np.clip(s_sq / (s_sq + prior.tau_sq), 0.0, 1.0))
        eb_score = (1.0 - shrink) * stats.weighted_mean + shrink * prior.global_mean
        posterior_sd = float(np.sqrt(shrink * prior.tau_sq))

        stars = list(star_ratings) if star_ratings is not None else []
        return ProductAggregate(
            product_asin=product_asin,
            corrected_score=round(float(np.clip(eb_score, SCORE_MIN, SCORE_MAX)), 2),
            uncertainty=round(posterior_sd, 3),
            review_count=stats.n,
            trust_weighted_score=round(stats.weighted_mean, 2),
            star_average=round(float(np.mean(stars)), 2) if stars else None,
            eb_shrinkage_factor=round(shrink, 3),
            aspect_summary=aggregate_aspects(aspect_sentiments),
        )

    def aggregate_all(
        self, reviews: Iterable[ReviewSignal]
    ) -> tuple[EBPrior, dict[str, ProductAggregate]]:
        """Fit the prior on every product and aggregate each one."""
        by_asin: dict[str, list[ReviewSignal]] = {}
        for review in reviews:
            by_asin.setdefault(review.product_asin, []).append(review)
        if not by_asin:
            raise ValueError("aggregate_all() needs at least one review")

        prior = self.fit(
            {
                asin: ([r.corrected_score for r in rs], [r.quality_weight for r in rs])
                for asin, rs in by_asin.items()
            }
        )
        aggregates = {
            asin: self.aggregate_product(
                [r.corrected_score for r in rs],
                [r.quality_weight for r in rs],
                [r.aspects for r in rs],
                star_ratings=[r.star_rating for r in rs],
                product_asin=asin,
            )
            for asin, rs in by_asin.items()
        }
        return prior, aggregates


def rank_products(aggregates: Mapping[str, ProductAggregate]) -> list[str]:
    """ASINs best-first: EB score desc, then more reviews, then lower uncertainty, then ASIN."""
    return sorted(
        aggregates,
        key=lambda a: (
            -aggregates[a].corrected_score,
            -aggregates[a].review_count,
            aggregates[a].uncertainty,
            a,
        ),
    )


def aggregate_aspects(aspect_sentiments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-aspect mention rate, sentiment counts, net sentiment, and majority label.

    ``net_sentiment`` = (positive − negative) / mentions, in [−1, 1] (drives the
    radar chart). Ties for the majority label resolve negative > positive >
    neutral, so a split verdict surfaces the complaint. Reviews whose aspect
    dict lacks a key (e.g. legacy rows) count as "not mentioned".
    """
    total = len(aspect_sentiments)
    summary: dict[str, Any] = {}
    for aspect in EARBUD_ASPECTS:
        mentions = [
            a[aspect]["sentiment"]
            for a in aspect_sentiments
            if isinstance(a.get(aspect), Mapping) and a[aspect].get("detected")
        ]
        counts = Counter(mentions)
        n = len(mentions)
        if n == 0:
            dominant = "not_mentioned"
        else:
            top = max(counts.values())
            dominant = next(s for s in _SENTIMENT_TIE_ORDER if counts.get(s, 0) == top)
        summary[aspect] = {
            "mention_count": n,
            "detected_fraction": round(n / total, 3) if total else 0.0,
            "positive": counts.get("positive", 0),
            "negative": counts.get("negative", 0),
            "neutral": counts.get("neutral", 0),
            "net_sentiment": (
                round((counts.get("positive", 0) - counts.get("negative", 0)) / n, 3) if n else 0.0
            ),
            "dominant_sentiment": dominant,
        }
    return summary
