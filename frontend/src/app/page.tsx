import { Gauge, Layers3, ShieldCheck } from "lucide-react"

import { ReviewAnalyzer } from "@/components/vera/review-analyzer"
import { roundOne } from "@/content/benchmarks"
import { pageMetadata } from "@/lib/metadata"

export const metadata = pageMetadata("See the experience behind the stars", "Read the experience behind an earbud review with aspect sentiment and uncertainty-aware scores.", "/")

const evidence = [
  { label: "Cross-validated MAE", value: roundOne.crossValidation.veraMae.toFixed(3), icon: Gauge },
  { label: "Interval coverage", value: `${roundOne.coverage.value}%`, icon: ShieldCheck },
  { label: "Median CPU analysis", value: `~${roundOne.latency.medianCpuSeconds}s`, icon: Layers3 },
]

export default function Home() {
  return (
    <>
      <header className="page-hero">
        <div className="font-mono text-xs uppercase tracking-[0.16em] text-primary">Review intelligence</div>
        <h1 className="display-title mt-5 max-w-5xl">See the experience behind the stars.</h1>
        <p className="mt-6 max-w-3xl text-pretty text-base leading-7 text-muted-foreground sm:text-lg">VERA reads the experience behind an earbud review, then shows its corrected score, aspect evidence, and uncertainty in one clear result.</p>
        <div className="mt-9 grid overflow-hidden rounded-2xl border border-border bg-card sm:w-fit sm:grid-cols-3">
          {evidence.map(({ label, value, icon: Icon }) => <div key={label} className="flex min-w-48 items-center gap-3 border-b border-border px-4 py-3 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0"><Icon className="size-4 text-primary" strokeWidth={1.5}/><div><p className="font-mono text-sm font-semibold tabular-nums">{value}</p><p className="text-xs text-muted-foreground">{label}</p></div></div>)}
        </div>
        <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.1em] text-muted-foreground">{roundOne.label}</p>
      </header>
      <ReviewAnalyzer />
    </>
  )
}
