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

      {/* Discovery Hub Banner */}
      <section className="mb-8 grid gap-4 sm:grid-cols-2">
        <a
          href="/advisor"
          className="group flex items-start gap-4 rounded-2xl border border-border/80 bg-card p-5 transition-all hover:border-primary/50 hover:bg-muted/30 hover:shadow-sm"
        >
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
            <Gauge className="size-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-foreground group-hover:text-primary transition-colors">
                Product Advisor &amp; RAG Match
              </span>
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">Top 3 India</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
              Query by points of interest (Audio, ANC, Connectivity, Budget) &amp; get Top 5 per bracket for Earbuds and Headphones.
            </p>
          </div>
        </a>

        <a
          href="/insights"
          className="group flex items-start gap-4 rounded-2xl border border-border/80 bg-card p-5 transition-all hover:border-primary/50 hover:bg-muted/30 hover:shadow-sm"
        >
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 group-hover:bg-blue-600 group-hover:text-white transition-colors">
            <Layers3 className="size-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-foreground group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                Earbuds vs. Headphones Study
              </span>
              <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold text-blue-600 dark:text-blue-400">5,196 Reviews</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
              Empirical hypotheses tests, Amazon rating inflation analysis (+0.65 bias), and 7-agent ML performance telemetry.
            </p>
          </div>
        </a>
      </section>

      <ReviewAnalyzer />
    </>
  )
}
