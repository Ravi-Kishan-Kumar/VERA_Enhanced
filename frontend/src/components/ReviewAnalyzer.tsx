"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { ApiError, api, errorMessage, pause } from "@/lib/api";
import type { Review, ReviewInput, ReviewTask } from "@/lib/types";
import { AspectRadar } from "./AspectRadar";
import { QualityFlags, ScoreCard } from "./ScoreCard";

const examples = [
  { label: "Mixed experience", stars: 5, text: "The sound is clear and the bass is great for the price. But the left earbud disconnects every few minutes, and the battery only lasts two hours. Comfortable enough for my commute, just unreliable." },
  { label: "Positive detail", stars: 4, text: "I've used these earbuds every day for three weeks. The sound is balanced, calls are clear, and they stay comfortable through a full workday. Battery life gets me through my commute and the noise cancellation works well on trains." },
];
type Phase = "idle" | "submitting" | "pending" | "processing" | "done" | "failed" | "paused";

export function ReviewAnalyzer() {
  const [text, setText] = useState("");
  const [stars, setStars] = useState("5");
  const [phase, setPhase] = useState<Phase>("idle");
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState("");
  const [reviewId, setReviewId] = useState<number | null>(null);
  const [slow, setSlow] = useState(false);
  const [retryAt, setRetryAt] = useState(0);
  const [cooldown, setCooldown] = useState(0);
  const controller = useRef<AbortController | null>(null);
  const result = useRef<HTMLDivElement>(null);
  const pending = ["submitting", "pending", "processing"].includes(phase);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!retryAt) return;
    const timer = setInterval(() => {
      const remaining = Math.max(0, Math.ceil((retryAt - Date.now()) / 1000));
      setCooldown(remaining);
      if (!remaining) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [retryAt]);

  function handleError(cause: unknown) {
    setError(errorMessage(cause));
    setPhase("paused");
    if (cause instanceof ApiError && cause.status === 429) {
      setCooldown(cause.retryAfterSeconds);
      setRetryAt(Date.now() + cause.retryAfterSeconds * 1000);
    }
  }

  async function poll(id: number, signal: AbortSignal) {
    const started = Date.now();
    while (!signal.aborted && Date.now() - started < 180_000) {
      const current = await api<Review>(`/reviews/${id}`, { signal });
      if (signal.aborted) return;
      if (current.status === "done") { setReview(current); setPhase("done"); setTimeout(() => result.current?.focus(), 0); return; }
      if (current.status === "failed") { setPhase("failed"); setError(current.error_message || "Analysis could not be completed. Please try submitting again later."); return; }
      if (current.status !== "pending" && current.status !== "processing") throw new Error("The service returned an unknown review status.");
      setPhase(current.status);
      setSlow(Date.now() - started >= 30_000);
      await pause(2_000, signal);
    }
    if (!signal.aborted) { setPhase("paused"); setError("This is taking longer than expected. Your review is saved; check again to resume waiting."); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || cooldown > 0) return;
    const form = new FormData(event.currentTarget);
    const cleanText = text.trim();
    if (cleanText.length < 20 || cleanText.length > 10_000) { setError("Enter between 20 and 10,000 characters after trimming whitespace."); return; }
    const votes = String(form.get("helpful_votes") || "");
    const verified = String(form.get("verified_purchase") || "");
    const input: ReviewInput = { text: cleanText, star_rating: Number(stars), helpful_votes: votes === "" ? null : Number(votes), verified_purchase: verified === "" ? null : verified === "true", product_title: String(form.get("product_title") || "").trim() || null, product_asin: String(form.get("product_asin") || "").trim() || null };
    controller.current?.abort();
    const abort = new AbortController(); controller.current = abort;
    setPhase("submitting"); setError(""); setReview(null); setReviewId(null); setSlow(false);
    try {
      // DB readiness only; do not claim that this certifies trained models or the worker.
      await api("/ready", { signal: abort.signal });
      const task = await api<ReviewTask>("/reviews", { method: "POST", body: JSON.stringify(input), signal: abort.signal });
      if (abort.signal.aborted) return;
      setReviewId(task.review_id);
      await poll(task.review_id, abort.signal);
    } catch (cause) { if (!abort.signal.aborted) handleError(cause); }
  }

  async function resume() {
    if (reviewId == null || cooldown > 0) return;
    controller.current?.abort(); const abort = new AbortController(); controller.current = abort;
    setPhase("pending"); setError(""); setSlow(false);
    try { await poll(reviewId, abort.signal); } catch (cause) { if (!abort.signal.aborted) handleError(cause); }
  }

  return <div className="analyzer-layout"><section className="input-panel"><div className="section-topline"><span className="eyebrow">01 / REVIEW INPUT</span><span className="mono muted">ENGLISH · EARBUDS</span></div><h2>Start with what they said.</h2><p className="panel-intro">Paste a review and its original star rating. VERA reads the experience behind it.</p>
    <form onSubmit={submit}><fieldset disabled={pending} className="form-fields"><div className="label-row"><label htmlFor="review-text">Review text</label><span id="review-count" className="mono muted">{text.length.toLocaleString()} / 10,000</span></div><textarea id="review-text" name="text" value={text} onChange={(event) => { setText(event.target.value); }} required minLength={20} maxLength={10_000} rows={7} aria-describedby="review-count" placeholder="The sound is incredible, but after a week the left earbud stopped connecting…"/>
      <div className="examples"><span>Try an example</span>{examples.map((example) => <button key={example.label} className="example-button" type="button" onClick={() => { setText(example.text); setStars(String(example.stars)); }}>{example.label} <span aria-hidden="true">↗</span></button>)}</div>
      <div className="rating-row"><label htmlFor="star-rating">Original star rating<span className="label-help">The rating attached to this review</span></label><select id="star-rating" name="star_rating" value={stars} onChange={(event) => setStars(event.target.value)}>{[1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5].map((n) => <option value={n} key={n}>{n.toFixed(1)} ★</option>)}</select></div>
      <details className="metadata"><summary>Product & review details <span>Optional <span aria-hidden="true">+</span></span></summary><p className="fine-print">Leave unknown details blank. Missing metadata is estimated using training-set values.</p><div className="metadata-grid"><label htmlFor="product-title">Product name<input id="product-title" name="product_title" maxLength={1000} placeholder="e.g. Wireless earbuds"/></label><label htmlFor="product-asin">Product ASIN<input id="product-asin" name="product_asin" maxLength={20} placeholder="e.g. B0ABC12345" autoCapitalize="characters"/></label><label htmlFor="helpful-votes">Helpful votes<input id="helpful-votes" name="helpful_votes" type="number" min={0} step={1} max={2147483647} placeholder="Unknown"/></label><label htmlFor="verified-purchase">Verified purchase<select id="verified-purchase" name="verified_purchase" defaultValue=""><option value="">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label></div></details>
      <button className="button primary analyze-button" type="submit" disabled={cooldown > 0}>{cooldown > 0 ? `Try again in ${cooldown}s` : pending ? "Analyzing review…" : "Analyze experience"}<span aria-hidden="true">↗</span></button><p className="fine-print privacy-note">Submissions are stored. Reviews linked to a product appear on its public detail page. Please remove personal information.</p>
    </fieldset></form>
    {(error || pending) && <div className={`analysis-status ${error ? "is-error" : ""}`} role={error ? "alert" : "status"}>{pending && <span className="loader" aria-hidden="true"/>}<div><strong>{pending ? phase === "submitting" ? "Submitting your review" : phase === "processing" ? "Reading the experience" : "Your review is in the queue" : "Analysis update"}</strong><p>{error || (slow ? "Still processing. Some analyses take longer when the service is starting up." : "Extracting signals, comparing the text, and calculating uncertainty.")}</p>{reviewId != null && <span className="mono fine-print">Review #{reviewId}</span>}{phase === "paused" && reviewId != null && <button className="button secondary" onClick={resume}>Check again</button>}{pending && <button className="text-button" onClick={() => { controller.current?.abort(); setPhase("paused"); setError("Waiting paused. Your submitted review continues processing."); }}>Stop waiting</button>}</div></div>}
  </section><div className="analysis-output" ref={result} tabIndex={-1}>{review && phase === "done" ? <><ScoreCard review={review}/><AspectRadar aspects={review.aspects}/><QualityFlags review={review}/>{review.product_asin && <Link href={`/products/${encodeURIComponent(review.product_asin)}`} className="text-link">View product & all reviews ↗</Link>}</> : <section className="awaiting-panel" aria-label="Analysis preview"><div className="section-topline"><span className="eyebrow">02 / EXPERIENCE SIGNAL</span><span className="badge">Awaiting review</span></div><div className="signal-art" aria-hidden="true"><div className="signal-axis"/><div className="signal-orbit orbit-one"/><div className="signal-orbit orbit-two"/><div className="signal-orbit orbit-three"/><div className="signal-core">V</div><span className="signal-label label-left">STAR RATING</span><span className="signal-label label-right">EXPERIENCE</span></div><h2>A rating is a click.<br/><span>An experience has context.</span></h2><p>Your analysis will bring the two together: a corrected score, its prediction interval, and the aspects that shaped it.</p><div className="output-key"><span><i className="key-dot blue"/>Corrected score</span><span><i className="key-dot green"/>Aspect sentiment</span><span><i className="key-dot amber"/>Uncertainty</span></div><Link href="/about" className="text-link">How VERA reads a review <span aria-hidden="true">↗</span></Link></section>}</div></div>;
}
