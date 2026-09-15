"use client"

import { AlertTriangle, ArrowRight, CheckCircle2, Info, Star } from "lucide-react"

import { NumberTicker } from "@/components/ui/number-ticker"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { displayScore } from "@/lib/format"
import type { Review } from "@/lib/types"
import { cn } from "@/lib/utils"

function scale(value: number) {
  return Math.max(0, Math.min(100, ((value - 1) / 4) * 100))
}

function DataLabel({ children, help }: { children: React.ReactNode; help: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
      {children}
      <Tooltip><TooltipTrigger aria-label={`About ${String(children)}`}><Info className="size-3.5" strokeWidth={1.5}/></TooltipTrigger><TooltipContent className="max-w-64">{help}</TooltipContent></Tooltip>
    </span>
  )
}

function ConfidenceInterval({ lower, upper, estimate }: { lower: number; upper: number; estimate: number }) {
  const left = scale(lower)
  const width = Math.max(1, scale(upper) - left)

  return (
    <figure className="grid gap-3 rounded-control border border-border bg-background p-4">
      <figcaption className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <DataLabel help="A model prediction interval. It communicates uncertainty; it is not a guarantee.">Prediction interval</DataLabel>
        <strong className="metric-number tabular-nums">{displayScore(lower)}-{displayScore(upper)}</strong>
      </figcaption>
      <div className="relative h-9" role="img" aria-label={`Corrected score ${displayScore(estimate)}; prediction interval ${displayScore(lower)} to ${displayScore(upper)} on a 1 to 5 scale`}>
        <div className="absolute inset-x-0 top-3 h-2 rounded-full bg-muted" />
        <div
          className="absolute top-2.5 h-3 rounded-full bg-primary/30"
          style={{ left: `${left}%`, width: `${width}%` }}
        />
        <span className="absolute top-1 size-6 -translate-x-1/2 rounded-full border-4 border-background bg-primary shadow-sm" style={{ left: `${scale(estimate)}%` }}/>
      </div>
      <div aria-hidden="true" className="flex justify-between font-mono text-[11px] text-muted-foreground">{[1, 2, 3, 4, 5].map((value) => <span key={value}>{value}.0</span>)}</div>
    </figure>
  )
}

export function ScoreResult({ review }: { review: Review }) {
  const corrected = review.corrected_score
  const delta = corrected == null ? null : corrected - review.star_rating

  return (
    <section data-testid="score-result" className="h-full p-5 sm:p-7" aria-labelledby={`result-${review.id}`}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <span className="eyebrow">Experience signal</span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-600/10 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300"><CheckCircle2 className="size-3.5" strokeWidth={1.5}/>Analysis complete</span>
      </div>
      <h2 id={`result-${review.id}`} className="sr-only">Review analysis result</h2>
      <div className="grid gap-6 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
        <div>
          <DataLabel help="The rating submitted with the source review.">Original rating</DataLabel>
          <p className="metric-number mt-2 text-4xl font-semibold tracking-[-0.04em] tabular-nums text-muted-foreground">{review.star_rating.toFixed(1)}<span className="text-base font-normal">/5</span></p>
          <div className="mt-2 flex gap-0.5 text-muted-foreground/35" aria-hidden="true">{Array.from({ length: 5 }, (_, index) => <Star key={index} className={cn("size-4", index < Math.round(review.star_rating) && "fill-current text-muted-foreground")} strokeWidth={1.5}/>)}</div>
        </div>
        <ArrowRight className="hidden size-5 text-muted-foreground sm:block" strokeWidth={1.5} aria-hidden="true" />
        <div>
          <DataLabel help="VERA's fusion of review text, aspect evidence, quality signals, and uncertainty.">VERA corrected</DataLabel>
          <p className="metric-number mt-2 text-5xl font-semibold tracking-[-0.055em] text-primary tabular-nums">
            {corrected == null ? "N/A" : <NumberTicker value={corrected} decimalPlaces={2} className="text-primary"/>}<span className="text-base font-normal text-muted-foreground">/5</span>
          </p>
          <p className={cn("mt-2 inline-flex rounded-full px-2.5 py-1 text-xs font-medium", delta == null ? "bg-muted text-muted-foreground" : delta >= 0 ? "bg-emerald-600/10 text-emerald-700 dark:text-emerald-300" : "bg-red-600/10 text-red-700 dark:text-red-300")}>{delta == null ? "Score unavailable" : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)} vs rating`}</p>
        </div>
      </div>
      {review.interval_lower != null && review.interval_upper != null && corrected != null && <div className="mt-7"><ConfidenceInterval lower={review.interval_lower} upper={review.interval_upper} estimate={corrected}/></div>}
      <p className="mt-5 border-l-2 border-primary/35 pl-4 text-sm leading-6 text-muted-foreground">{review.explanation || "The service did not return an explanation for this result."}</p>
      <dl className="mt-6 grid grid-cols-3 divide-x divide-border border-y border-border py-4">
        <div className="px-3 first:pl-0"><dt className="text-xs text-muted-foreground">Interval confidence</dt><dd className="metric-number mt-1 font-semibold tabular-nums">{review.confidence_value == null ? "N/A" : `${Math.round(review.confidence_value * 100)}%`}</dd></div>
        <div className="px-3"><dt className="text-xs text-muted-foreground">Quality weight</dt><dd className="metric-number mt-1 font-semibold tabular-nums">{displayScore(review.review_quality)}</dd></div>
        <div className="px-3 pr-0"><dt className="text-xs text-muted-foreground">Star-text gap</dt><dd className="metric-number mt-1 font-semibold tabular-nums">{displayScore(review.star_text_gap)}</dd></div>
      </dl>
      <p className="mt-3 text-xs leading-5 text-muted-foreground">Confidence describes interval narrowness, not the probability that a review is correct. The star-text gap is calculated before fusion.</p>
    </section>
  )
}

export function QualityFlags({ review }: { review: Review }) {
  const flags = review.flags || {}
  const items: string[] = []
  if (flags.is_english === false) items.push("Non-English text: this model is calibrated for English.")
  if (flags.is_earbud === false) items.push("This review may be outside the earbud domain.")
  if (flags.star_inflated === true) items.push("The star rating is higher than the text-derived experience.")
  if (flags.star_deflated === true) items.push("The star rating is lower than the text-derived experience.")
  if (flags.has_url === true) items.push("The review contains a link.")
  if (Array.isArray(flags.imputed_fields) && flags.imputed_fields.length) items.push(`Missing metadata estimated from training data: ${flags.imputed_fields.filter((value): value is string => typeof value === "string").map((value) => value.replaceAll("_", " ")).join(", ")}.`)

  return (
    <section className="rounded-card border border-border bg-card p-5 sm:p-6" aria-labelledby={`quality-${review.id}`}>
      <div className="flex gap-3">
        {items.length ? <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-600 dark:text-amber-400" strokeWidth={1.5}/> : <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600 dark:text-emerald-400" strokeWidth={1.5}/>} 
        <div><h3 id={`quality-${review.id}`} className="text-base font-semibold">Reading this result</h3>{items.length ? <ul className="mt-3 grid gap-2 text-sm text-muted-foreground">{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="mt-2 text-sm text-muted-foreground">No additional quality flags were returned.</p>}</div>
      </div>
      <p className="mt-4 border-t border-border pt-4 text-xs leading-5 text-muted-foreground">Quality is a weighting signal. It does not verify a purchase or prove that a review is authentic.</p>
    </section>
  )
}
