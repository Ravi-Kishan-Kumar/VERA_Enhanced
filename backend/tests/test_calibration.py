"""Conformal and empirical-Bayes regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.ml.calibration.conformal import ConformalPredictor
from app.ml.calibration.empirical_bayes import EmpiricalBayesAggregator, ReviewSignal, rank_products


def test_normalized_conformal_interval_is_clipped_and_widens(tmp_path: Path) -> None:
    path = tmp_path / "qhat.json"
    path.write_text(
        json.dumps(
            {
                "method": "normalized",
                "q_hat": 2.0,
                "nominal_coverage": 0.9,
                "sigma_floor": 0.1,
            }
        ),
        encoding="utf-8",
    )
    predictor = ConformalPredictor(path)

    low_std = predictor.predict_interval(1.05, ensemble_std=0.0)
    high_std = predictor.predict_interval(3.0, ensemble_std=0.5)

    assert low_std[0] == 1.0
    assert 1.0 <= low_std[1] <= 5.0
    assert high_std[1] - high_std[0] > low_std[1] - low_std[0]
    assert 0.0 <= high_std[2] <= 1.0


def test_eb_applies_noise_floor_to_identical_scores() -> None:
    aggregator = EmpiricalBayesAggregator()
    aggregator.fit(
        {
            "A": ([4.0, 4.0], [1.0, 1.0]),
            "B": ([2.0, 2.5], [1.0, 1.0]),
            "C": ([3.0, 3.5], [1.0, 1.0]),
        }
    )
    aggregate = aggregator.aggregate_product([4.0, 4.0], [1.0, 1.0], [{}, {}])

    assert aggregate.eb_shrinkage_factor > 0.0
    assert aggregate.uncertainty > 0.0


def test_aggregate_all_ranks_more_reliable_product_above_single_five_star() -> None:
    signals = [
        ReviewSignal("one", 5.0, 1.0, 5.0),
        *[ReviewSignal("many", 4.6, 1.0, 4.6) for _ in range(20)],
        *[ReviewSignal(f"baseline-{index}", 3.0, 1.0, 3.0) for index in range(20)],
    ]
    _, aggregates = EmpiricalBayesAggregator().aggregate_all(signals)

    assert aggregates["one"].eb_shrinkage_factor > aggregates["many"].eb_shrinkage_factor
    assert rank_products(aggregates)[0] == "many"
