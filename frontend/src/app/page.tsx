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
      <header className="page-hero grid items-end gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div><p className="eyebrow">Review intelligence</p><h1 className="display-title mt-3">See the experience behind the stars.</h1></div>
        <p className="max-w-md text-pretty text-base leading-7 text-muted-foreground lg:pb-1">Analyze an earbud review for corrected scores, aspect evidence, and uncertainty you can see.</p>
      </header>
      <section className="mb-6 overflow-hidden rounded-card border border-border bg-card/70" aria-label={`${roundOne.label} model evidence`}>
        <p className="border-b border-border px-5 py-2.5 text-xs font-medium text-muted-foreground">{roundOne.label}</p>
        <div className="grid sm:grid-cols-3">{evidence.map(({ label, value, icon: Icon }) => <div key={label} className="flex min-h-20 items-center gap-3 border-b border-border px-5 py-4 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0"><Icon className="size-4 text-primary" strokeWidth={1.5}/><div><p className="metric-number text-base font-semibold">{value}</p><p className="text-sm text-muted-foreground">{label}</p></div></div>)}</div>
      </section>
      <ReviewAnalyzer />
    </>
  )
}
