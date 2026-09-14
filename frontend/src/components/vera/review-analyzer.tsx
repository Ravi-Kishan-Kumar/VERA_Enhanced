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
  { label: "Mixed reliability", stars: 3.5, text: "The sound is clear and the bass is great for the price. But the left earbud disconnects every few minutes, and the battery only lasts two hours. Comfortable enough for my commute, just unreliable." },
  { label: "Detailed praise", stars: 4.5, text: "I have used these earbuds every day for three weeks. The sound is balanced, calls are clear, and they stay comfortable through a full workday. Battery life covers my commute and noise cancellation works well on trains." },
  { label: "Rating mismatch", stars: 5, text: "Five stars for the fast delivery, but the earbuds themselves feel flimsy. The microphone sounds distant, the fit loosens while running, and Bluetooth drops whenever my phone is in my pocket." },
] as const

type Phase = "idle" | "submitting" | "pending" | "processing" | "done" | "failed" | "paused"

function ProcessingState({ phase, pollCount, reviewId, slow }: { phase: Phase; pollCount: number; reviewId: number | null; slow: boolean }) {
  const stages = ["Secure submission", "Queue review", "Read text signals", "Resolve aspect evidence", "Calibrate score"]
  const active = phase === "submitting" ? 0 : phase === "pending" ? 1 : Math.min(4, 2 + Math.floor(pollCount / 2))

  return (
    <section className="animate-in fade-in slide-in-from-bottom-1 rounded-2xl border border-border bg-card p-6 duration-200 motion-reduce:animate-none" aria-live="polite" aria-busy="true">
      <div className="flex items-center gap-3"><LoaderCircle className="size-5 animate-spin text-primary motion-reduce:animate-none" strokeWidth={1.5}/><div><h2 className="text-lg font-semibold">Reading the experience</h2><p className="text-sm text-muted-foreground">Status updates come from the analysis worker.</p></div></div>
      <ol className="mt-7 grid gap-1">
        {stages.map((stage, index) => <li key={stage} className={cn("flex min-h-11 items-center gap-3 rounded-[10px] px-3 text-sm", index === active && "bg-primary/8 text-foreground", index > active && "text-muted-foreground")}>
          {index < active ? <CircleCheck className="size-4 text-primary" strokeWidth={1.5}/> : index === active ? <LoaderCircle className="size-4 animate-spin text-primary motion-reduce:animate-none" strokeWidth={1.5}/> : <Circle className="size-4" strokeWidth={1.5}/>}<span>{stage}</span>{index === active && <span className="ml-auto font-mono text-[11px] uppercase tracking-wider text-primary">Active</span>}
        </li>)}
      </ol>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4 text-xs text-muted-foreground"><span>{slow ? "The worker is taking longer than usual; your review remains saved." : "No artificial progress percentages — VERA reports the worker state."}</span>{reviewId != null && <span className="font-mono">Review #{reviewId}</span>}</div>
    </section>
  )
}

function EmptySignal() {
  return (
    <section className="flex min-h-[31rem] flex-col justify-between rounded-2xl border border-dashed border-border bg-card/55 p-6 sm:p-8">
      <div className="flex items-center justify-between gap-3"><span className="font-mono text-xs uppercase tracking-[0.12em] text-muted-foreground">Experience signal</span><span className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground">Awaiting review</span></div>
      <div className="py-12"><div className="mb-8 flex items-center gap-3" aria-hidden="true"><span className="h-px flex-1 bg-border"/><span className="grid size-12 place-items-center rounded-xl border border-primary/25 bg-primary/8 font-mono font-semibold text-primary">V</span><span className="h-px flex-1 bg-border"/></div><h2 className="max-w-md text-3xl font-semibold tracking-[-0.04em]">A rating is a click. An experience has context.</h2><p className="mt-4 max-w-lg text-sm leading-6 text-muted-foreground">Your result will connect the two with a corrected score, prediction interval, aspect evidence, and quality signals.</p></div>
      <Link href="/about" className="inline-flex min-h-11 w-fit items-center gap-2 rounded-[10px] text-sm font-medium text-primary hover:underline hover:underline-offset-4">How VERA reads a review<ArrowUpRight className="size-4" strokeWidth={1.5}/></Link>
    </section>
  )
}

export function ReviewAnalyzer() {
  const [text, setText] = useState("")
  const [stars, setStars] = useState(4)
  const [phase, setPhase] = useState<Phase>("idle")
  const [review, setReview] = useState<Review | null>(null)
  const [error, setError] = useState("")
  const [reviewId, setReviewId] = useState<number | null>(null)
  const [slow, setSlow] = useState(false)
  const [retryAt, setRetryAt] = useState(0)
  const [cooldown, setCooldown] = useState(0)
  const [pollCount, setPollCount] = useState(0)
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
      setCooldown(cause.retryAfterSeconds)
      setRetryAt(Date.now() + cause.retryAfterSeconds * 1_000)
      toast.warning("Analysis limit reached", { description: `Try again in ${cause.retryAfterSeconds} seconds.` })
    } else if (cause instanceof ApiError && cause.status === 503) {
      toast.warning("Analysis service is warming up", { description: "Your draft is safe. Please retry shortly." })
    } else {
      toast.error("Analysis paused", { description: message })
    }
  }

  async function poll(id: number, signal: AbortSignal) {
    const started = Date.now()
    while (!signal.aborted && Date.now() - started < 180_000) {
      const current = await api<Review>(`/reviews/${id}`, { signal })
      if (signal.aborted) return
      if (current.status === "done") { setReview(current); setPhase("done"); window.setTimeout(() => result.current?.focus(), 0); return }
      if (current.status === "failed") { setPhase("failed"); setError(current.error_message || "Analysis could not be completed. Please try again later."); return }
      if (current.status !== "pending" && current.status !== "processing") throw new Error("The service returned an unknown review status.")
      setPhase(current.status)
      setPollCount((count) => count + 1)
      setSlow(Date.now() - started >= 30_000)
      await pause(2_000, signal)
    }
    if (!signal.aborted) { setPhase("paused"); setError("This is taking longer than expected. Your review is saved; check again to resume waiting.") }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending || cooldown > 0) return
    const form = new FormData(event.currentTarget)
    const cleanText = text.trim()
    if (cleanText.length < 20 || cleanText.length > 10_000) { setError("Enter between 20 and 10,000 characters after trimming whitespace."); return }
    const votes = String(form.get("helpful_votes") || "")
    const verified = String(form.get("verified_purchase") || "")
    const input: ReviewInput = { text: cleanText, star_rating: stars, helpful_votes: votes === "" ? null : Number(votes), verified_purchase: verified === "" ? null : verified === "true", product_title: String(form.get("product_title") || "").trim() || null, product_asin: String(form.get("product_asin") || "").trim() || null }
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    setPhase("submitting"); setError(""); setReview(null); setReviewId(null); setSlow(false); setPollCount(0)
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
    setPhase("pending"); setError(""); setSlow(false)
    try { await poll(reviewId, abort.signal) } catch (cause) { if (!abort.signal.aborted) handleError(cause) }
  }

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <section className="rounded-2xl border border-border bg-card p-5 sm:p-7" aria-labelledby="review-input-title">
        <span className="font-mono text-xs uppercase tracking-[0.12em] text-muted-foreground">Review input</span><h2 id="review-input-title" className="mt-2 text-2xl font-semibold tracking-[-0.03em]">Start with what they said.</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Paste an English earbud review and its original star rating.</p>
        <form className="mt-7" onSubmit={submit}><fieldset disabled={pending} className="grid gap-6">
          <div className="grid gap-2"><div className="flex items-end justify-between gap-4"><Label htmlFor="review-text">Review text</Label><span id="review-count" className="font-mono text-xs text-muted-foreground">{text.length.toLocaleString()} / 10,000</span></div><Textarea id="review-text" name="text" value={text} onChange={(event) => setText(event.target.value)} required minLength={20} maxLength={10_000} rows={8} aria-describedby="review-count review-privacy" placeholder="The sound is detailed, but after a week the left earbud stopped connecting…" className="min-h-48 resize-y rounded-[10px] bg-background px-3 py-3 leading-6"/></div>
          <div><p className="mb-2 text-xs font-medium text-muted-foreground">Try an example</p><div className="flex flex-wrap gap-2">{examples.map((example) => <Button key={example.label} type="button" variant="outline" size="sm" className="rounded-[10px]" onClick={() => { setText(example.text); setStars(example.stars) }}>{example.label}</Button>)}</div></div>
          <div className="grid gap-2"><Label htmlFor="star-rating">Original star rating</Label><StarRating value={stars} onChange={setStars} disabled={pending}/></div>
          <Accordion type="single" collapsible><AccordionItem value="metadata"><AccordionTrigger className="min-h-11 rounded-[10px] px-1">Product and review details <span className="ml-2 text-xs font-normal text-muted-foreground">Optional</span></AccordionTrigger><AccordionContent className="grid gap-4 pt-3 sm:grid-cols-2"><div className="grid gap-2"><Label htmlFor="product-title">Product name</Label><Input id="product-title" name="product_title" maxLength={1_000} placeholder="Wireless earbuds"/></div><div className="grid gap-2"><Label htmlFor="product-asin">Product ASIN</Label><Input id="product-asin" name="product_asin" maxLength={20} autoCapitalize="characters" placeholder="B0ABC12345"/></div><div className="grid gap-2"><Label htmlFor="helpful-votes">Helpful votes</Label><Input id="helpful-votes" name="helpful_votes" type="number" min={0} step={1} max={2_147_483_647} placeholder="Unknown"/></div><div className="grid gap-2"><Label htmlFor="verified-purchase">Verified purchase</Label><select id="verified-purchase" name="verified_purchase" defaultValue="" className="h-9 rounded-[10px] border border-input bg-background px-3 text-sm"><option value="">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></div></AccordionContent></AccordionItem></Accordion>
          <Button size="lg" type="submit" disabled={cooldown > 0} className="h-12 rounded-[10px]">{cooldown > 0 ? `Try again in ${cooldown}s` : pending ? <><LoaderCircle className="animate-spin motion-reduce:animate-none"/>Analyzing review</> : <>Analyze review<ArrowUpRight/></>}</Button>
          <p id="review-privacy" className="text-xs leading-5 text-muted-foreground">Submissions are stored. Reviews linked to a product can appear on its public detail page. Remove personal information before submitting.</p>
        </fieldset></form>
        {error && <div className="mt-5 rounded-xl border border-destructive/25 bg-destructive/6 p-4" role="alert"><p className="text-sm font-medium">Analysis update</p><p className="mt-1 text-sm text-muted-foreground">{error}</p><div className="mt-3 flex flex-wrap gap-2">{phase === "paused" && reviewId != null && <Button type="button" size="sm" variant="outline" onClick={resume} disabled={cooldown > 0}><RotateCcw/>Check again</Button>}{reviewId != null && <span className="self-center font-mono text-xs text-muted-foreground">Review #{reviewId}</span>}</div></div>}
        {pending && <Button type="button" variant="ghost" size="sm" className="mt-3" onClick={() => { controller.current?.abort(); setPhase("paused"); setError("Waiting paused. Your submitted review continues processing.") }}><Pause/>Stop waiting</Button>}
      </section>
      <div ref={result} tabIndex={-1} data-testid="analysis-output" className="grid gap-5 outline-none">
        {review && phase === "done" ? <div className="animate-in fade-in slide-in-from-bottom-1 grid gap-5 duration-200 motion-reduce:animate-none"><ScoreResult review={review}/><AspectBreakdown aspects={review.aspects}/><QualityFlags review={review}/>{review.product_asin && <Button asChild variant="outline" className="h-11 justify-between rounded-[10px]"><Link href={`/products/${encodeURIComponent(review.product_asin)}`}>View product and all reviews<ArrowUpRight/></Link></Button>}</div> : pending ? <ProcessingState phase={phase} pollCount={pollCount} reviewId={reviewId} slow={slow}/> : <EmptySignal/>}
      </div>
    </div>
  )
}
