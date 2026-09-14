"use client";
import { motion, useReducedMotion, useSpring, useTransform } from "framer-motion";
import { useEffect } from "react";
import type { Review } from "@/lib/types";
import { score } from "@/lib/types";

function AnimatedScore({ target }: { target: number }) {
  const reduced = useReducedMotion();
  const spring = useSpring(0, { stiffness: 80, damping: 25 });
  const display = useTransform(spring, (value) => value.toFixed(2));
  useEffect(() => { if (reduced) spring.jump(target); else spring.set(target); }, [target, reduced, spring]);
  return <><span className="sr-only">{score(target)}</span><motion.span aria-hidden="true">{display}</motion.span></>;
}

export function ConfidenceBar({ lower, upper, estimate }: { lower: number; upper: number; estimate: number }) {
  const x = (value: number) => 24 + ((Math.min(5, Math.max(1, value)) - 1) / 4) * 452;
  return <figure className="interval"><svg viewBox="0 0 500 70" role="img" aria-label={`Corrected score ${score(estimate)}; prediction interval ${score(lower)} to ${score(upper)} on a 1 to 5 scale`}>
    <line x1="24" x2="476" y1="24" y2="24" stroke="var(--border-active)" strokeWidth="2"/>
    {[1, 2, 3, 4, 5].map((n) => <g key={n}><line x1={x(n)} x2={x(n)} y1="19" y2="29" stroke="var(--border-active)"/><text x={x(n)} y="59" textAnchor="middle" fill="var(--text-secondary)" fontSize="12">{n.toFixed(1)}</text></g>)}
    <line x1={x(lower)} x2={x(upper)} y1="24" y2="24" stroke="var(--accent-primary)" strokeOpacity=".4" strokeWidth="14" strokeLinecap="round"/>
    <line x1={x(lower)} x2={x(lower)} y1="14" y2="34" stroke="var(--accent-primary)" strokeWidth="2"/><line x1={x(upper)} x2={x(upper)} y1="14" y2="34" stroke="var(--accent-primary)" strokeWidth="2"/>
    <circle cx={x(estimate)} cy="24" r="6" fill="var(--text-primary)" stroke="var(--bg-surface)" strokeWidth="2"/>
  </svg><figcaption><span>Prediction interval</span><strong>{score(lower)} — {score(upper)}</strong></figcaption></figure>;
}

export function ScoreCard({ review }: { review: Review }) {
  const delta = review.corrected_score == null ? null : review.corrected_score - review.star_rating;
  return <section className="score-card" aria-labelledby={`result-${review.id}`}><div className="section-topline"><span className="eyebrow">02 / EXPERIENCE SIGNAL</span><span className="badge success">Analysis complete</span></div>
    <h2 id={`result-${review.id}`} className="sr-only">Review analysis result</h2>
    <div className="score-comparison"><div><span className="data-label">Original rating</span><div className="score-number raw-score">{review.star_rating.toFixed(1)}<small>/5</small></div><span className="star-string" aria-hidden="true">{"★".repeat(Math.round(review.star_rating))}</span></div><span className="score-arrow" aria-hidden="true">→</span><div><span className="data-label corrected-label">VERA corrected</span><div className="score-number corrected-score">{review.corrected_score == null ? "—" : <AnimatedScore target={review.corrected_score}/>}<small>/5</small></div><span className="delta">{delta == null ? "Score unavailable" : `${delta > 0 ? "+" : ""}${delta.toFixed(2)} from original rating`}</span></div></div>
    {review.interval_lower != null && review.interval_upper != null && review.corrected_score != null && <ConfidenceBar lower={review.interval_lower} upper={review.interval_upper} estimate={review.corrected_score}/>}
    <div className="result-explanation"><span className="signal-icon" aria-hidden="true">↳</span><p>{review.explanation || "The corrected score combines text experience, aspect sentiment, consistency, and review quality."}</p></div>
    <div className="result-stat-grid"><div><span className="data-label">Interval confidence</span><strong>{review.confidence_value == null ? "—" : `${Math.round(review.confidence_value * 100)}%`}</strong></div><div><span className="data-label">Review quality weight</span><strong>{score(review.review_quality)}</strong></div><div><span className="data-label">Star–text gap</span><strong>{score(review.star_text_gap)}</strong></div></div>
    <p className="fine-print">Interval confidence measures interval narrowness, not the probability this review is correct. The star–text gap compares the original rating with the text model, before fusion.</p>
  </section>;
}

export function QualityFlags({ review }: { review: Review }) {
  const flags = review.flags || {};
  const items: string[] = [];
  if (flags.is_english === false) items.push("Non-English text: this model is calibrated for English.");
  if (flags.is_earbud === false) items.push("This review may be outside the earbud domain.");
  if (flags.star_inflated === true) items.push("The star rating is higher than the text-derived experience.");
  if (flags.star_deflated === true) items.push("The star rating is lower than the text-derived experience.");
  if (flags.has_url === true) items.push("The review contains a link.");
  if (Array.isArray(flags.imputed_fields) && flags.imputed_fields.length) items.push(`Missing metadata estimated from training data: ${flags.imputed_fields.filter((v): v is string => typeof v === "string").map((v) => v.replaceAll("_", " ")).join(", ")}.`);
  return <section className="quality-flags"><h3>Reading this result</h3>{items.length ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No additional quality flags were returned.</p>}<p className="fine-print">Quality is a weighting signal. It does not verify a purchase or prove a review is authentic.</p></section>;
}
