"use client"

import { ArrowUpRight, Circle, CircleCheck, LoaderCircle, Pause, RotateCcw } from "lucide-react"
import Link from "next/link"
import { useEffect, useRef, useState, type FormEvent } from "react"
import { toast } from "sonner"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { AspectBreakdown } from "@/components/vera/aspect-breakdown"
import { QualityFlags, ScoreResult } from "@/components/vera/score-result"
import { StarRating } from "@/components/vera/star-rating"
import { ApiError, api, errorMessage, pause } from "@/lib/api"
import type { Review, ReviewInput, ReviewTask } from "@/lib/types"
import { cn } from "@/lib/utils"

const examples = [
  { label: "Mixed reliability", stars: 3.5, category: "earbuds", text: "The sound is clear and the bass is great for the price. But the left earbud disconnects every few minutes, and the battery only lasts two hours. Comfortable enough for my commute, just unreliable." },
  { label: "Detailed praise", stars: 4.5, category: "earbuds", text: "I have used these earbuds every day for three weeks. The sound is balanced, calls are clear, and they stay comfortable through a full workday. Battery life covers my commute and noise cancellation works well on trains." },
  { label: "Rating mismatch", stars: 5, category: "earbuds", text: "Five stars for the fast delivery, but the earbuds themselves feel flimsy. The microphone sounds distant, the fit loosens while running, and Bluetooth drops whenever my phone is in my pocket." },
  { label: "Sarcastic review", stars: 5, category: "headphones", text: "Oh great, another pair of earbuds that disconnect every ten minutes. Just what I needed. I love how the right one dies after an hour and the app crashes whenever I try to change the settings. Truly a premium experience, worth every penny. Can't wait to buy a second pair." },
] as const

type Phase = "idle" | "submitting" | "pending" | "processing" | "done" | "failed" | "paused"
type FieldErrors = { text?: string; stars?: string }

const MAX_POLLING_MS = 180_000
const INITIAL_POLL_DELAY_MS = 1_500
const MAX_POLL_DELAY_MS = 8_000

function isLifecycleStatus(status: string): status is Review["status"] {
  return status === "pending" || status === "processing" || status === "done" || status === "failed"
}

function pollDelay(attempt: number) {
  return Math.min(MAX_POLL_DELAY_MS, Math.round(INITIAL_POLL_DELAY_MS * 1.5 ** attempt))
}

function workerFailureMessage(errorMessage: string | null) {
  const normalized = errorMessage?.toLowerCase() ?? ""
  const modelUnavailable = ["model", "artifact", "onnx", "tokenizer", "checkpoint", "not loaded", "missing"].some((term) => normalized.includes(term))
  return modelUnavailable
    ? "The analysis model is not available on the worker. No score was generated. Please retry after model service is restored."
    : "The analysis worker could not complete this review. No score was generated. Please try again later."
}

function ProcessingState({ phase, reviewId, slow }: { phase: Phase; reviewId: number | null; slow: boolean }) {
  const stages = ["Secure submission", "Wait in queue", "Worker processing", "Retrieve completed result"]
  const active = phase === "submitting" ? 0 : phase === "pending" ? 1 : 2

  return (
    <section className="animate-in fade-in flex min-h-[30rem] flex-col justify-center p-1 duration-200 motion-reduce:animate-none" aria-live="polite" aria-busy="true">
      <div className="flex items-center gap-3"><LoaderCircle className="size-5 animate-spin text-primary motion-reduce:animate-none" strokeWidth={1.5}/><div><h2 className="font-heading text-2xl font-semibold">Reading the experience</h2><p className="text-sm text-muted-foreground">Status updates come from the analysis worker.</p></div></div>
      <ol className="mt-7 grid gap-1">
        {stages.map((stage, index) => <li key={stage} className={cn("flex min-h-11 items-center gap-3 rounded-control px-3 text-sm", index === active && "bg-primary/8 text-foreground", index > active && "text-muted-foreground")}>
          {index < active ? <CircleCheck className="size-4 text-primary" strokeWidth={1.5}/> : index === active ? <LoaderCircle className="size-4 animate-spin text-primary motion-reduce:animate-none" strokeWidth={1.5}/> : <Circle className="size-4" strokeWidth={1.5}/>}<span>{stage}</span>{index === active && <span className="ml-auto text-xs font-medium text-primary">Active</span>}
        </li>)}
      </ol>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4 text-xs text-muted-foreground"><span>{slow ? "The worker is taking longer than usual; your review remains saved." : "VERA reports only confirmed queue and worker states."}</span>{reviewId != null && <span className="font-mono">Review #{reviewId}</span>}</div>
    </section>
  )
}

function EmptySignal() {
  return (
    <section className="flex min-h-[30rem] flex-col justify-center">
      <span className="mb-6 w-fit rounded-control bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary">Awaiting review</span>
      <h2 className="max-w-md font-heading text-3xl font-semibold leading-tight tracking-[-0.025em]">Your analysis will appear here.</h2>
      <p className="mt-4 max-w-md text-base leading-7 text-muted-foreground">Submit a review to see the corrected score, prediction interval, aspect evidence, and explanation.</p>
      <Link href="/about" className="mt-7 inline-flex min-h-11 w-fit items-center gap-2 rounded-control text-sm font-semibold text-primary hover:underline hover:underline-offset-4">Read the methodology<ArrowUpRight className="size-4" strokeWidth={1.5}/></Link>
    </section>
  )
}

export function ReviewAnalyzer() {
  const [text, setText] = useState("")
  const [stars, setStars] = useState(4)
  const [category, setCategory] = useState<"earbuds" | "headphones">("earbuds")
  const [phase, setPhase] = useState<Phase>("idle")
  const [review, setReview] = useState<Review | null>(null)
  const [error, setError] = useState("")
  const [errorTitle, setErrorTitle] = useState("Analysis update")
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [reviewId, setReviewId] = useState<number | null>(null)
  const [slow, setSlow] = useState(false)
  const [retryAt, setRetryAt] = useState(0)
  const [cooldown, setCooldown] = useState(0)
  const controller = useRef<AbortController | null>(null)
  const result = useRef<HTMLDivElement>(null)
  const pending = ["submitting", "pending", "processing"].includes(phase)

  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => {
    if (!retryAt) return
    const update = () => setCooldown(Math.max(0, Math.ceil((retryAt - Date.now()) / 1000)))
    const timer = window.setInterval(update, 1_000)
    return () => window.clearInterval(timer)
  }, [retryAt])

  function handleError(cause: unknown) {
    const message = errorMessage(cause)
    setError(message)
    setPhase("paused")
    if (cause instanceof ApiError && cause.status === 429) {
      setErrorTitle("Analysis limit reached")
      setCooldown(cause.retryAfterSeconds)
      setRetryAt(Date.now() + cause.retryAfterSeconds * 1_000)
      toast.warning("Analysis limit reached", { description: `Try again in ${cause.retryAfterSeconds} seconds.` })
    } else if (cause instanceof ApiError && cause.status === 503) {
      setErrorTitle("Service temporarily unavailable")
      setError("The API or its database is temporarily unavailable. Your draft is safe; no analysis was submitted by this attempt.")
      toast.warning("Service temporarily unavailable", { description: "Your draft is safe. Please retry shortly." })
    } else if (cause instanceof ApiError && cause.status === 0) {
      setErrorTitle("Connection interrupted")
      toast.error("Connection interrupted", { description: message })
    } else {
      setErrorTitle("Analysis paused")
      toast.error("Analysis paused", { description: message })
    }
  }

  async function poll(id: number, signal: AbortSignal) {
    const started = Date.now()
    let attempt = 0
    while (!signal.aborted && Date.now() - started < MAX_POLLING_MS) {
      const current = await api<ReviewTask>(`/reviews/${id}/status`, { signal })
      if (signal.aborted) return
      if (!isLifecycleStatus(current.status)) throw new Error("The service returned an unknown review status.")
      if (current.status === "done") {
        const completed = await api<Review>(`/reviews/${id}`, { signal })
        if (completed.status !== "done") throw new Error("The completed review result is not available yet.")
        setReview(completed)
        setPhase("done")
        window.setTimeout(() => result.current?.focus(), 0)
        return
      }
      if (current.status === "failed") {
        const failed = await api<Review>(`/reviews/${id}`, { signal })
        setPhase("failed")
        setErrorTitle("Analysis could not be completed")
        setError(workerFailureMessage(failed.error_message))
        return
      }
      setPhase(current.status)
      setSlow(Date.now() - started >= 30_000)
      await pause(pollDelay(attempt), signal)
      attempt += 1
    }
    if (!signal.aborted) { setPhase("paused"); setErrorTitle("Still processing"); setError("This is taking longer than expected. Your review is saved; check again to resume waiting.") }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending || cooldown > 0) return
    const form = new FormData(event.currentTarget)
    const cleanText = text.trim()
    const validation: FieldErrors = {}
    if (cleanText.length === 0) validation.text = "Enter a review before starting analysis."
    else if (cleanText.length < 20) validation.text = "Use at least 20 characters after trimming whitespace."
    else if (cleanText.length > 10_000) validation.text = "Keep the review at or below 10,000 characters."
    if (!Number.isFinite(stars) || stars < 1 || stars > 5 || stars * 2 % 1 !== 0) validation.stars = "Choose a rating from 1 to 5 in half-star steps."
    setFieldErrors(validation)
    if (Object.keys(validation).length) return
    const votes = String(form.get("helpful_votes") || "")
    const verified = String(form.get("verified_purchase") || "")
    const input: ReviewInput = { text: cleanText, star_rating: stars, helpful_votes: votes === "" ? null : Number(votes), verified_purchase: verified === "" ? null : verified === "true", product_title: String(form.get("product_title") || "").trim() || null, product_asin: String(form.get("product_asin") || "").trim() || null, product_category: category }
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    setPhase("submitting"); setError(""); setErrorTitle("Analysis update"); setReview(null); setReviewId(null); setSlow(false)
    try {
      await api("/ready", { signal: abort.signal })
      const task = await api<ReviewTask>("/reviews", { method: "POST", body: JSON.stringify(input), signal: abort.signal })
      if (abort.signal.aborted) return
      setReviewId(task.review_id)
      await poll(task.review_id, abort.signal)
    } catch (cause) { if (!abort.signal.aborted) handleError(cause) }
  }

  async function resume() {
    if (reviewId == null || cooldown > 0) return
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    setPhase("pending"); setError(""); setErrorTitle("Analysis update"); setSlow(false)
    try { await poll(reviewId, abort.signal) } catch (cause) { if (!abort.signal.aborted) handleError(cause) }
  }

  return (
    <div className="panel grid items-stretch overflow-hidden lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
      <section className="border-b border-border p-5 sm:p-7 lg:border-b-0 lg:border-r lg:p-8" aria-labelledby="review-input-title">
        <p className="eyebrow">Analyze a review</p><h2 id="review-input-title" className="mt-2 font-heading text-3xl font-semibold leading-tight tracking-[-0.025em]">Start with what they said.</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Paste an earbud or headphone review and choose its original rating.</p>
        <form className="mt-6" onSubmit={submit}><fieldset disabled={pending} className="grid gap-5">
          <div className="grid gap-2"><div className="flex items-end justify-between gap-4"><Label htmlFor="review-text">Review text</Label><span id="review-count" className="metric-number text-xs text-muted-foreground">{text.length.toLocaleString()} / 10,000</span></div><Textarea id="review-text" name="text" value={text} onChange={(event) => { setText(event.target.value); if (fieldErrors.text) setFieldErrors((current) => ({ ...current, text: undefined })) }} rows={7} aria-invalid={Boolean(fieldErrors.text)} aria-describedby={`review-count review-privacy${fieldErrors.text ? " review-text-error" : ""}`} placeholder="The sound is detailed, but after a week the left earbud stopped connecting..." className="min-h-44 resize-y rounded-control bg-background px-3 py-3 leading-6"/>{fieldErrors.text && <p id="review-text-error" className="text-sm text-destructive" role="alert">{fieldErrors.text}</p>}</div>
          <div><p className="mb-2 text-xs font-medium text-muted-foreground">Try an example</p><div className="flex flex-wrap gap-2">{examples.map((example) => <Button key={example.label} type="button" variant="outline" size="sm" className="rounded-control" onClick={() => { setText(example.text); setStars(example.stars); setCategory(example.category as "earbuds" | "headphones"); setFieldErrors({}) }}>{example.label}</Button>)}</div></div>
          <div className="grid gap-2"><Label htmlFor="star-rating">Original star rating</Label><StarRating value={stars} onChange={(value) => { setStars(value); if (fieldErrors.stars) setFieldErrors((current) => ({ ...current, stars: undefined })) }} disabled={pending}/>{fieldErrors.stars && <p className="text-sm text-destructive" role="alert">{fieldErrors.stars}</p>}</div>
          <div className="grid gap-2"><Label htmlFor="product-category">Review is about</Label><div className="flex gap-2">{(["earbuds", "headphones"] as const).map((cat) => <Button key={cat} type="button" variant={category === cat ? "default" : "outline"} size="sm" className={cn("h-10 flex-1 rounded-control capitalize", category === cat && "pointer-events-none")} onClick={() => setCategory(cat)}>{cat === "earbuds" ? "🎧 Earbuds / TWS" : "🎧 Headphones"}</Button>)}</div></div>
          <Accordion type="single" collapsible><AccordionItem value="metadata"><AccordionTrigger className="min-h-11 rounded-control px-1">Product and review details <span className="ml-2 text-xs font-normal text-muted-foreground">Optional</span></AccordionTrigger><AccordionContent className="grid gap-4 pt-3 sm:grid-cols-2"><div className="grid gap-2"><Label htmlFor="product-title">Product name</Label><Input id="product-title" name="product_title" maxLength={1_000} placeholder="Wireless earbuds"/></div><div className="grid gap-2"><Label htmlFor="product-asin">Product ASIN</Label><Input id="product-asin" name="product_asin" maxLength={20} autoCapitalize="characters" placeholder="B0ABC12345"/></div><div className="grid gap-2"><Label htmlFor="helpful-votes">Helpful votes</Label><Input id="helpful-votes" name="helpful_votes" type="number" min={0} step={1} max={2_147_483_647} placeholder="Unknown"/></div><div className="grid gap-2"><Label htmlFor="verified-purchase">Verified purchase</Label><select id="verified-purchase" name="verified_purchase" defaultValue="" className="h-11 rounded-control border border-input bg-background px-3 text-sm"><option value="">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></div></AccordionContent></AccordionItem></Accordion>
          <Button size="lg" type="submit" disabled={pending || cooldown > 0} className="h-12 rounded-control">{cooldown > 0 ? `Try again in ${cooldown}s` : pending ? <><LoaderCircle className="animate-spin motion-reduce:animate-none"/>Analyzing review</> : <>Analyze review<ArrowUpRight/></>}</Button>
          <p id="review-privacy" className="text-xs leading-5 text-muted-foreground">Submissions are stored. Product-linked reviews may appear publicly. Remove personal information before submitting.</p>
        </fieldset></form>
        {error && <div className="mt-5 rounded-control border border-destructive/25 bg-destructive/6 p-4" role="alert"><p className="text-sm font-medium">{errorTitle}</p><p className="mt-1 text-sm text-muted-foreground">{error}</p><div className="mt-3 flex flex-wrap gap-2">{phase === "paused" && reviewId != null && <Button type="button" size="sm" variant="outline" onClick={resume} disabled={cooldown > 0}><RotateCcw/>Check again</Button>}{reviewId != null && <span className="self-center font-mono text-xs text-muted-foreground">Review #{reviewId}</span>}</div></div>}
        {pending && <Button type="button" variant="ghost" size="sm" className="mt-3" onClick={() => { controller.current?.abort(); setPhase("paused"); setError("Waiting paused. Your submitted review continues processing.") }}><Pause/>Stop waiting</Button>}
      </section>
      <div ref={result} tabIndex={-1} data-testid="analysis-output" aria-live="polite" className="grid min-w-0 gap-5 bg-muted/25 p-5 outline-none sm:p-7 lg:p-8">
        {review && phase === "done" ? <div className="animate-in fade-in slide-in-from-bottom-1 grid gap-5 duration-200 motion-reduce:animate-none"><ScoreResult review={review}/><AspectBreakdown aspects={review.aspects}/><QualityFlags review={review}/>{review.product_asin && <Button asChild variant="outline" className="h-11 justify-between rounded-control"><Link href={`/products/${encodeURIComponent(review.product_asin)}`}>View product and all reviews<ArrowUpRight/></Link></Button>}</div> : pending ? <ProcessingState phase={phase} reviewId={reviewId} slow={slow}/> : <EmptySignal/>}
      </div>
    </div>
  )
}
