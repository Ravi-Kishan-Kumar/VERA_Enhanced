"use client"

import { ArrowLeft, ArrowRight, LoaderCircle, Scale } from "lucide-react"
import Link from "next/link"
import { useEffect, useMemo, useRef, useState } from "react"

import { AspectBreakdown } from "@/components/vera/aspect-breakdown"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError, api, errorMessage } from "@/lib/api"
import { score, type ProductDetail as Detail, type Review } from "@/lib/types"

const REVIEWS_PAGE = 20
type ReviewFilter = "all" | "inflated" | "deflated" | "high-quality"

function ProductError({ asin, message, notFound, retry }: { asin: string; message: string; notFound: boolean; retry: () => void }) {
  return <div className="py-24 text-center"><p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">{asin}</p><h1 className="mt-3 text-3xl font-semibold">{notFound ? "Product not found" : "Unable to load product"}</h1><p className="mx-auto mt-3 max-w-lg text-sm text-muted-foreground">{notFound ? "No completed reviews are associated with this ASIN." : message}</p><div className="mt-6 flex justify-center gap-2"><Button asChild variant="outline"><Link href="/products"><ArrowLeft/>Rankings</Link></Button>{!notFound && <Button onClick={retry}>Try again</Button>}</div></div>
}

function ReviewCard({ review }: { review: Review }) {
  const [expanded, setExpanded] = useState(false)
  const needsExpansion = review.text.length > 320
  const visibleText = expanded || !needsExpansion ? review.text : `${review.text.slice(0, 320).trimEnd()}…`
  return <li className="rounded-xl border border-border bg-background p-4"><header className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><Badge variant="secondary" className="font-mono">Original {review.star_rating.toFixed(1)}</Badge><ArrowRight className="size-3.5 text-muted-foreground"/><Badge className="font-mono">VERA {score(review.corrected_score)}</Badge></div>{review.interval_lower != null && review.interval_upper != null && <span className="font-mono text-xs text-muted-foreground">PI {score(review.interval_lower)}–{score(review.interval_upper)}</span>}</header><p className="mt-4 text-sm leading-6">{visibleText}</p>{needsExpansion && <Button type="button" variant="link" className="mt-1 h-9 px-0 text-xs" onClick={() => setExpanded((value) => !value)}>{expanded ? "Show less" : "Show full review"}</Button>}{review.explanation && <p className="mt-3 border-l-2 border-primary/25 pl-3 text-xs leading-5 text-muted-foreground">{review.explanation}</p>}</li>
}

export function ProductDetail({ asin }: { asin: string }) {
  const [product, setProduct] = useState<Detail | null>(null)
  const [reviews, setReviews] = useState<Review[]>([])
  const [filter, setFilter] = useState<ReviewFilter>("all")
  const [error, setError] = useState<{ asin: string; message: string; notFound: boolean } | null>(null)
  const [loadMoreError, setLoadMoreError] = useState("")
  const [loadingMore, setLoadingMore] = useState(false)
  const [reload, setReload] = useState(0)
  const loadMoreController = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    loadMoreController.current?.abort()
    api<Detail>(`/products/${encodeURIComponent(asin)}?reviews_limit=${REVIEWS_PAGE}`, { signal: controller.signal }).then((detail) => { setProduct(detail); setReviews(detail.reviews); setError(null) }).catch((cause) => { if (!controller.signal.aborted) setError({ asin, message: errorMessage(cause), notFound: cause instanceof ApiError && cause.status === 404 }) })
    return () => { controller.abort(); loadMoreController.current?.abort() }
  }, [asin, reload])

  const visibleProduct = product?.asin === asin ? product : null
  const filteredReviews = useMemo(() => reviews.filter((review) => {
    if (filter === "inflated") return review.flags?.star_inflated === true
    if (filter === "deflated") return review.flags?.star_deflated === true
    if (filter === "high-quality") return (review.review_quality ?? 0) >= 0.75
    return true
  }), [filter, reviews])

  async function loadMore() {
    if (!visibleProduct || loadingMore) return
    const controller = new AbortController()
    loadMoreController.current = controller
    setLoadingMore(true); setLoadMoreError("")
    try {
      const next = await api<Detail>(`/products/${encodeURIComponent(asin)}?reviews_limit=${REVIEWS_PAGE}&reviews_offset=${reviews.length}`, { signal: controller.signal })
      if (!controller.signal.aborted) { setReviews((current) => [...current, ...next.reviews]); setProduct(next) }
    } catch (cause) { if (!controller.signal.aborted) setLoadMoreError(errorMessage(cause)) } finally { if (!controller.signal.aborted) setLoadingMore(false) }
  }

  if (error?.asin === asin) return <ProductError asin={asin} message={error.message} notFound={error.notFound} retry={() => { setError(null); setReload((value) => value + 1) }}/>
  if (!visibleProduct) return <div className="grid gap-5 py-16" aria-label="Loading product" role="status"><Skeleton className="h-7 w-36"/><Skeleton className="h-20 w-3/4"/><div className="grid gap-4 sm:grid-cols-3"><Skeleton className="h-36 rounded-2xl"/><Skeleton className="h-36 rounded-2xl"/><Skeleton className="h-36 rounded-2xl"/></div></div>

  const shrinkPct = visibleProduct.eb_shrinkage_factor == null ? null : Math.round(visibleProduct.eb_shrinkage_factor * 100)
  return (
    <>
      <header className="pb-10 pt-12 sm:pb-12 sm:pt-16"><Button asChild variant="ghost" className="-ml-3"><Link href="/products"><ArrowLeft/>All rankings</Link></Button><p className="mt-8 font-mono text-xs uppercase tracking-[0.14em] text-primary">{visibleProduct.asin}</p><h1 className="mt-3 max-w-4xl text-balance text-[clamp(2.4rem,5vw,4.7rem)] font-semibold leading-[0.98] tracking-[-0.055em]">{visibleProduct.title || "Untitled product"}</h1></header>
      {visibleProduct.corrected_score == null ? <div className="rounded-2xl border border-dashed border-border bg-card/55 p-10 text-center"><h2 className="text-xl font-semibold">Not scored yet</h2><p className="mt-2 text-sm text-muted-foreground">This product&apos;s reviews are still being analyzed.</p></div> : <>
        <section className="grid gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-4" aria-label="Product score summary">
          <div className="bg-primary p-6 text-primary-foreground"><p className="text-xs font-medium uppercase tracking-wider opacity-75">VERA score</p><p className="mt-3 font-mono text-5xl font-semibold tracking-[-0.05em]">{score(visibleProduct.corrected_score)}</p><p className="mt-2 font-mono text-xs opacity-75">±{score(visibleProduct.uncertainty)} uncertainty</p></div>
          <div className="bg-card p-6"><p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Star average</p><p className="mt-3 font-mono text-4xl font-semibold">{score(visibleProduct.star_average)}</p><p className="mt-2 text-xs text-muted-foreground">What the ratings claim</p></div>
          <div className="bg-card p-6"><p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Rank</p><p className="mt-3 font-mono text-4xl font-semibold">#{visibleProduct.rank_position ?? "—"}</p><p className="mt-2 text-xs text-muted-foreground">{visibleProduct.review_count} analyzed review{visibleProduct.review_count === 1 ? "" : "s"}</p></div>
          <div className="bg-card p-6"><div className="flex items-center gap-2"><Scale className="size-4 text-primary"/><p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Shrinkage</p></div><p className="mt-3 font-mono text-4xl font-semibold">{shrinkPct == null ? "—" : `${shrinkPct}%`}</p><p className="mt-2 text-xs leading-5 text-muted-foreground">Pull toward the global mean for sparse or noisy evidence</p></div>
        </section>
        <div className="mt-8 grid items-start gap-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]"><AspectBreakdown summary={visibleProduct.aspect_summary}/><section className="rounded-2xl border border-border bg-card p-5 sm:p-6" aria-labelledby="reviews-title"><div className="flex flex-wrap items-end justify-between gap-3"><div><span className="font-mono text-xs uppercase tracking-[0.12em] text-muted-foreground">Review evidence</span><h2 id="reviews-title" className="mt-2 text-xl font-semibold">Analyzed reviews</h2></div><span className="font-mono text-xs text-muted-foreground">{reviews.length} / {visibleProduct.reviews_total}</span></div><div className="mt-5 grid gap-2 sm:grid-cols-[auto_1fr] sm:items-center"><label htmlFor="review-filter" className="text-xs font-medium text-muted-foreground">Filter evidence</label><select id="review-filter" value={filter} onChange={(event) => setFilter(event.target.value as ReviewFilter)} className="h-10 rounded-[10px] border border-input bg-background px-3 text-sm sm:justify-self-end"><option value="all">All loaded reviews</option><option value="inflated">Stars higher than text</option><option value="deflated">Stars lower than text</option><option value="high-quality">High quality weight</option></select></div>{filteredReviews.length ? <ul className="mt-5 grid gap-3">{filteredReviews.map((review) => <ReviewCard key={review.id} review={review}/>)}</ul> : <p className="mt-5 rounded-xl bg-muted p-6 text-sm text-muted-foreground">No loaded reviews match this filter.</p>}{loadMoreError && <div role="alert" className="mt-4 rounded-xl border border-destructive/25 p-4 text-sm"><p>{loadMoreError}</p><Button variant="link" className="mt-1 h-8 px-0" onClick={loadMore}>Try loading more again</Button></div>}{reviews.length < visibleProduct.reviews_total && <Button type="button" variant="outline" className="mt-5 w-full" disabled={loadingMore} onClick={loadMore}>{loadingMore ? <><LoaderCircle className="animate-spin motion-reduce:animate-none"/>Loading reviews</> : "Show more reviews"}</Button>}</section></div>
      </>}
    </>
  )
}
