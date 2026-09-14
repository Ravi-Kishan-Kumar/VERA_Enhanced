"use client";

/**
 * Sortable, paginated product rankings (PRD §16.2 ProductTable).
 * Each row: rank + rank change, star average vs EB-corrected score,
 * uncertainty, review count, and the strongest aspect signals.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiPage, errorMessage } from "@/lib/api";
import { ASPECTS, aspectName, score, type Product } from "@/lib/types";
import { EmptyState, ErrorState, LoadingState } from "./State";

type SortKey = "corrected_score" | "star_average" | "review_count" | "uncertainty";
type Order = "asc" | "desc";

const PAGE_SIZE = 25;
const COLUMNS: { key: SortKey; label: string; defaultOrder: Order }[] = [
  { key: "corrected_score", label: "Stars → VERA", defaultOrder: "desc" },
  { key: "star_average", label: "Star avg", defaultOrder: "desc" },
  { key: "uncertainty", label: "± Uncertainty", defaultOrder: "asc" },
  { key: "review_count", label: "Reviews", defaultOrder: "desc" },
];

function RankChange({ current, previous }: { current: number | null; previous?: number | null }) {
  if (current == null || previous == null) return <span className="rank-change same" aria-label="New">NEW</span>;
  const moved = previous - current;
  if (moved === 0) return <span className="rank-change same" aria-label="No change">—</span>;
  return moved > 0 ? (
    <span className="rank-change up" aria-label={`Up ${moved}`}>▲{moved}</span>
  ) : (
    <span className="rank-change down" aria-label={`Down ${-moved}`}>▼{-moved}</span>
  );
}

/** Up to two strongest positive and negative aspects (by net sentiment, min. 1 mention). */
function AspectChips({ product }: { product: Product }) {
  const summary = product.aspect_summary;
  if (!summary) return <span className="muted">—</span>;
  const mentioned = ASPECTS.map((key) => ({ key, s: summary[key] })).filter((a) => a.s && a.s.mention_count > 0);
  const positives = mentioned.filter((a) => a.s!.net_sentiment > 0).sort((a, b) => b.s!.net_sentiment - a.s!.net_sentiment).slice(0, 2);
  const negatives = mentioned.filter((a) => a.s!.net_sentiment < 0).sort((a, b) => a.s!.net_sentiment - b.s!.net_sentiment).slice(0, 2);
  if (!positives.length && !negatives.length) return <span className="muted">—</span>;
  return (
    <div className="aspect-icons">
      {positives.map((a) => (
        <span key={a.key} className="aspect-chip positive">+ {aspectName(a.key)}</span>
      ))}
      {negatives.map((a) => (
        <span key={a.key} className="aspect-chip negative">− {aspectName(a.key)}</span>
      ))}
    </div>
  );
}

export function ProductTable() {
  const [sortBy, setSortBy] = useState<SortKey>("corrected_score");
  const [order, setOrder] = useState<Order>("desc");
  const [page, setPage] = useState(0);
  const [data, setData] = useState<{ items: Product[]; total: number } | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ sort_by: sortBy, order, limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) });
    apiPage<Product>(`/products?${query}`, { signal: controller.signal })
      .then((result) => { setData(result); setError(""); })
      .catch((cause) => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => controller.abort();
  }, [sortBy, order, page, reload]);

  const sort = useCallback((key: SortKey) => {
    const column = COLUMNS.find((c) => c.key === key)!;
    setData(null);
    setError("");
    setOrder((current) => (key === sortBy ? (current === "desc" ? "asc" : "desc") : column.defaultOrder));
    setSortBy(key);
    setPage(0);
  }, [sortBy]);

  if (error) return <ErrorState message={error} retry={() => { setError(""); setData(null); setReload((n) => n + 1); }} />;
  if (!data) return <LoadingState label="Loading rankings" />;
  if (data.total === 0) {
    return <EmptyState title="No ranked products yet">Products appear here after their first review with a product ASIN is analyzed.</EmptyState>;
  }

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const ariaSort = (key: SortKey) => (key === sortBy ? (order === "asc" ? "ascending" : "descending") : "none");

  return (
    <>
      <p className="table-scroll-hint">Scroll sideways to see every ranking measure.</p>
      <div className="table-wrap" role="region" aria-label="Scrollable product rankings" tabIndex={0}>
        <table className="product-table">
          <caption className="sr-only">Earbud products ranked by VERA corrected score</caption>
          <thead>
            <tr>
              <th scope="col">Rank</th>
              <th scope="col">Product</th>
              {COLUMNS.map((column) => (
                <th key={column.key} scope="col" className="num" aria-sort={ariaSort(column.key)}>
                  <button type="button" onClick={() => sort(column.key)}>
                    {column.label} {column.key === sortBy ? (order === "desc" ? "↓" : "↑") : ""}
                  </button>
                </th>
              ))}
              <th scope="col">Aspects</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((product) => (
              <tr key={product.asin}>
                <td>
                  <div className="rank-cell mono">
                    {product.rank_position ?? "—"}
                    <RankChange current={product.rank_position} previous={product.previous_rank_position} />
                  </div>
                </td>
                <td>
                  <Link className="product-name" href={`/products/${encodeURIComponent(product.asin)}`}>
                    <strong>{product.title || "Untitled product"}</strong>
                    <span className="mono fine-print">{product.asin}</span>
                  </Link>
                </td>
                <td className="num">
                  <span className="star-vs">
                    <span className="from">{score(product.star_average)}</span>
                    <span className="to">{score(product.corrected_score)}</span>
                  </span>
                </td>
                <td className="num">{score(product.star_average)}</td>
                <td className="num">±{score(product.uncertainty)}</td>
                <td className="num"><span className="badge">{product.review_count}</span></td>
                <td><AspectChips product={product} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <nav className="pagination" aria-label="Pagination">
        <span className="mono">Page {page + 1} / {pages} · {data.total} products</span>
        <div>
          <button className="button secondary" type="button" disabled={page === 0} onClick={() => { setData(null); setPage((p) => p - 1); }}>← Prev</button>
          <button className="button secondary" type="button" disabled={page + 1 >= pages} onClick={() => { setData(null); setPage((p) => p + 1); }}>Next →</button>
        </div>
      </nav>
    </>
  );
}
