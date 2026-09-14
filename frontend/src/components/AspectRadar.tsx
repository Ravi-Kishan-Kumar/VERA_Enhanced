"use client";
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from "recharts";
import { ASPECTS, aspectName, type Aspect, type AspectKey, type AspectSummary, type Sentiment } from "@/lib/types";

export function AspectRadar({ aspects, summary }: { aspects?: Partial<Record<AspectKey, Aspect>> | null; summary?: Partial<Record<AspectKey, AspectSummary>> | null }) {
  const rows = ASPECTS.map((key) => {
    const aggregate = summary?.[key];
    const aspect = aspects?.[key];
    const detected = aggregate ? aggregate.mention_count > 0 : Boolean(aspect?.detected);
    const sentiment: Sentiment = detected ? aggregate?.dominant_sentiment || aspect?.sentiment || "neutral" : "not_mentioned";
    const value = aggregate ? aggregate.net_sentiment : sentiment === "positive" ? 1 : sentiment === "negative" ? -1 : 0;
    return { key, label: aspectName(key), detected, sentiment, value: value + 1, mentions: aggregate?.mention_count };
  });
  const detected = rows.filter((row) => row.detected);
  return <section className="aspect-section" aria-labelledby="aspect-title"><div className="section-topline"><h2 id="aspect-title">What the review{summary ? "s reveal" : " reveals"}</h2><span className="mono muted">{detected.length} / 10 aspects</span></div>
    <div className="aspect-layout">{detected.length >= 3 ? <div className="radar-wrap" aria-hidden="true"><ResponsiveContainer width="100%" height={290}><RadarChart data={detected} outerRadius="65%"><PolarGrid stroke="var(--border-active)"/><PolarAngleAxis dataKey="label" tick={{ fill: "var(--text-secondary)", fontSize: 10 }}/><PolarRadiusAxis domain={[0, 2]} ticks={[0, 1, 2]} tick={false} axisLine={false}/><Radar name="Sentiment" dataKey="value" stroke="var(--accent-primary)" fill="var(--accent-primary)" fillOpacity={0.12} isAnimationActive={false} dot={(props) => { const { cx, cy, payload } = props as { cx?: number; cy?: number; payload?: typeof rows[number] }; return <circle key={payload?.key} cx={cx} cy={cy} r={4} fill={`var(--sentiment-${payload?.sentiment || "neutral"})`}/>; }}/></RadarChart></ResponsiveContainer><p className="fine-print chart-caption">Center: negative · middle: neutral · edge: positive.<br/>Only mentioned aspects are plotted.</p></div> : <div className="radar-empty"><span aria-hidden="true">◎</span><p>{detected.length === 0 ? "No earbud aspects detected yet." : "A radar needs at least three detected aspects."}</p><p className="fine-print">Missing mentions are not neutral sentiment.</p></div>}
    <ul className="aspect-list">{rows.map((row) => <li key={row.key}><span className={`aspect-dot ${row.sentiment}`} aria-hidden="true"/><span>{row.label}</span><span className={`sentiment-label ${row.sentiment}`}>{row.detected ? row.sentiment : "Not mentioned"}{row.mentions != null && row.detected ? ` · ${row.mentions}` : ""}</span></li>)}</ul></div>
  </section>;
}
