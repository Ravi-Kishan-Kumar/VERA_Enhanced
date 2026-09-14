"use client";

/** Product detail: EB aggregate, aspect breakdown, and paginated analyzed reviews (PRD §16.4). */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiError, api, errorMessage } from "@/lib/api";
import { score, type ProductDetail as Detail, type Review } from "@/lib/types";
import { AspectRadar } from "./AspectRadar";
import { EmptyState, ErrorState, LoadingState } from "./State";

const REVIEWS_PAGE = 20;

function ReviewItem({ review }: { review: Review }) {
  return (
    <li className="review-item">
      <header>
        <span className="star-vs mono">
          <span className="from">{review.star_rating.toFixed(1)}★</span>
          <span className="to">{score(review.corrected_score)}</span>
        </span>
        {review.interval_lower != null && review.interval_upper != null && (
          <span className="badge">[{score(review.interval_lower)} – {score(review.interval_upper)}]</span>
        )}
      </header>
      <p>{review.text.length > 420 ? `${review.text.slice(0, 420)}…` : review.text}</p>
      {review.explanation && <p className="fine-print">{review.explanation}</p>}
    </li>
  );
}

export function ProductDetail({ asin }: { asin: string }) {
  const [product, setProduct] = useState<Detail | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [error, setError] = useState<{ asin: string; message: string; notFound: boolean } | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<{ asin: string; message: string } | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [reload, setReload] = useState(0);
  const loadMoreController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    loadMoreController.current?.abort();
    api<Detail>(`/products/${encodeURIComponent(asin)}?reviews_limit=${REVIEWS_PAGE}`, { signal: controller.signal })
      .then((detail) => { setProduct(detail); setReviews(detail.reviews); })
      .catch((cause) => {
        if (!controller.signal.aborted) setError({ asin, message: errorMessage(cause), notFound: cause instanceof ApiError && cause.status === 404 });
      });
    return () => { controller.abort(); loadMoreController.current?.abort(); };
  }, [asin, reload]);

  async function loadMore() {
    if (!visibleProduct || loadingMore) return;
    const controller = new AbortController();
    loadMoreController.current = controller;
    setLoadingMore(true);
    setLoadMoreError(null);
    try {
      const next = await api<Detail>(`/products/${encodeURIComponent(asin)}?reviews_limit=${REVIEWS_PAGE}&reviews_offset=${reviews.length}`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setReviews((current) => [...current, ...next.reviews]);
      setProduct(next);
    } catch (cause) {
      if (!controller.signal.aborted) setLoadMoreError({ asin, message: errorMessage(cause) });
    } finally {
      setLoadingMore(false);
    }
  }

  const visibleProduct = product?.asin === asin ? product : null;
  const visibleError = error?.asin === asin ? error : null;
  const visibleLoadMoreError = loadMoreError?.asin === asin ? loadMoreError : null;

  if (visibleError?.notFound) return <EmptyState title="Product not found">No reviews have been submitted for ASIN {asin}.</EmptyState>;
  if (visibleError) return <ErrorState message={visibleError.message} retry={() => { setError(null); setReload((n) => n + 1); }} />;
  if (!visibleProduct) return <LoadingState label="Loading product" />;

  const shrinkPct = visibleProduct.eb_shrinkage_factor == null ? null : Math.round(visibleProduct.eb_shrinkage_factor * 100);

  return (
    <>
      <div className="detail-header">
        <Link href="/products" className="text-link">← All products</Link>
        <div className="eyebrow"><span className="tiny-square" aria-hidden="true" /> {visibleProduct.asin}</div>
        <h1>{visibleProduct.title || "Untitled product"}</h1>
      </div>

      {visibleProduct.corrected_score == null ? (
        <EmptyState title="Not scored yet">This product&apos;s reviews are still being analyzed.</EmptyState>
      ) : (
        <>
          <div className="detail-grid">
            <div className="stat highlight">
              <span className="data-label">VERA score</span>
              <strong>{score(visibleProduct.corrected_score)}</strong>
              <p>±{score(visibleProduct.uncertainty)} posterior uncertainty</p>
            </div>
            <div className="stat">
              <span className="data-label">Star average</span>
              <strong>{score(visibleProduct.star_average)}</strong>
              <p>What the ratings claim</p>
            </div>
            <div className="stat">
              <span className="data-label">Rank</span>
              <strong>#{visibleProduct.rank_position ?? "—"}</strong>
              <p>{visibleProduct.review_count} analyzed review{visibleProduct.review_count === 1 ? "" : "s"}</p>
            </div>
            <div className="stat">
              <span className="data-label">Shrinkage</span>
              <strong>{shrinkPct == null ? "—" : `${shrinkPct}%`}</strong>
              <p>Pull toward the global mean (more with fewer, noisier reviews)</p>
            </div>
          </div>

          <div className="detail-columns">
            <AspectRadar summary={visibleProduct.aspect_summary} />
            <section className="panel" aria-labelledby="reviews-title">
              <div className="section-topline">
                <h2 id="reviews-title">Analyzed reviews</h2>
                <span className="mono muted">{reviews.length} / {visibleProduct.reviews_total}</span>
              </div>
              {reviews.length ? (
                <ul className="review-list">{reviews.map((review) => <ReviewItem key={review.id} review={review} />)}</ul>
              ) : (
                <p className="muted">No completed reviews yet.</p>
              )}
              {visibleLoadMoreError && <div className="load-more-error" role="alert"><p>{visibleLoadMoreError.message}</p><button className="text-button" type="button" onClick={loadMore}>Try loading more again</button></div>}
              {reviews.length < visibleProduct.reviews_total && <button className="button secondary load-more-button" type="button" disabled={loadingMore} onClick={loadMore}>
                {loadingMore ? <><span className="loader" aria-hidden="true" /> Loading reviews…</> : "Load more reviews"}
              </button>}
            </section>
          </div>
        </>
      )}
    </>
  );
}
