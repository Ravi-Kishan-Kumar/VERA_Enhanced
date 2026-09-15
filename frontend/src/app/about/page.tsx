import { ArrowRight, CircleHelp, Scale, ShieldCheck, Tags } from "lucide-react"
import Link from "next/link"

import { PipelineDiagram } from "@/components/vera/pipeline-diagram"
import { Button } from "@/components/ui/button"
import { benchmarkRounds, type CompletedBenchmarkRound } from "@/content/benchmarks"
import { pageMetadata } from "@/lib/metadata"

export const metadata = pageMetadata("Methodology", "How VERA combines review signals, aspect sentiment, and honest uncertainty, with transparent model limitations.", "/about")

const toc = [
  ["pipeline", "Signal pipeline"],
  ["uncertainty", "Honest uncertainty"],
  ["rankings", "Fair rankings"],
  ["labels", "Labels and validation"],
  ["benchmarks", "Benchmarks"],
  ["limitations", "Limitations"],
] as const

function BenchmarkResults({ round }: { round: CompletedBenchmarkRound }) {
  const rows = [
    { label: "15-fold grouped CV MAE", vera: `${round.crossValidation.veraMae} ± ${round.crossValidation.veraStd}`, reference: `Stars ${round.crossValidation.starsMae} ± ${round.crossValidation.starsStd}` },
    { label: "Held-out test MAE", vera: String(round.heldOut.veraMae), reference: `Stars ${round.heldOut.starsMae}` },
    { label: "90% interval coverage", vera: `${round.coverage.value}%`, reference: `n = ${round.coverage.reviews}` },
    { label: "Label agreement κ", vera: String(round.agreement.selfKappa), reference: `LLM ref. ${round.agreement.referenceLlmKappa.toFixed(3)}` },
    { label: "Median CPU latency", vera: `≈ ${round.latency.medianCpuSeconds}s`, reference: `max ${round.latency.maxCpuSeconds}s / ${round.latency.reviews}` },
  ]

  return (
    <div className="mt-5 overflow-hidden rounded-card border border-border bg-card">
      <dl className="divide-y divide-border sm:hidden">
        {rows.map((row) => (
          <div key={row.label} className="grid gap-3 p-4">
            <dt className="text-sm font-medium">{row.label}</dt>
            <dd className="grid grid-cols-2 gap-3 text-sm">
              <span><span className="block text-xs text-muted-foreground">VERA</span><span className="metric-number mt-1 block font-semibold">{row.vera}</span></span>
              <span><span className="block text-xs text-muted-foreground">Reference</span><span className="metric-number mt-1 block text-muted-foreground">{row.reference}</span></span>
            </dd>
          </div>
        ))}
      </dl>
      <table className="hidden w-full text-left text-sm sm:table">
        <caption className="sr-only">{round.label} benchmark measurements</caption>
        <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground"><tr><th className="px-4 py-3 font-medium">Measure</th><th className="px-4 py-3 text-right font-medium">VERA</th><th className="px-4 py-3 text-right font-medium">Reference</th></tr></thead>
        <tbody className="divide-y divide-border">{rows.map((row) => <tr key={row.label}><td className="px-4 py-3">{row.label}</td><td className="metric-number px-4 py-3 text-right font-semibold">{row.vera}</td><td className="metric-number px-4 py-3 text-right text-muted-foreground">{row.reference}</td></tr>)}</tbody>
      </table>
      <div className="grid gap-1 border-t border-border bg-muted/35 px-4 py-3 text-xs text-muted-foreground sm:grid-cols-2">
        <p>VERA won {round.crossValidation.foldsWon} grouped folds.</p>
        <p className="sm:text-right">Wilcoxon p = {round.crossValidation.wilcoxon}.</p>
      </div>
    </div>
  )
}

function MethodSection({ id, icon, title, children }: { id: string; icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-28 border-t border-border pt-10">
      <div className="max-w-[68ch]">
        <div className="flex items-center gap-2 text-primary">{icon}<span className="eyebrow">VERA method</span></div>
        <h2 className="section-heading mt-3">{title}</h2>
        <div className="mt-4 leading-7 text-muted-foreground">{children}</div>
      </div>
    </section>
  )
}

export default function AboutPage() {
  return (
    <>
      <header className="page-hero grid items-end gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(18rem,0.7fr)]">
        <div><p className="eyebrow">Methodology</p><h1 className="display-title mt-3 max-w-4xl">How VERA reads a review.</h1></div>
        <p className="max-w-xl text-base leading-7 text-muted-foreground">Text-derived experience, calibrated uncertainty, and limitations shown in plain language.</p>
      </header>

      <div className="grid items-start gap-10 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <nav aria-label="On this page" className="sticky top-24 hidden border-l border-border pl-4 lg:block">
          <p className="mb-2 text-xs font-medium text-muted-foreground">On this page</p>
          {toc.map(([href, label]) => <a key={href} href={`#${href}`} className="block min-h-11 border-l-2 border-transparent px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-foreground">{label}</a>)}
        </nav>

        <article className="min-w-0 pb-10">
          <section id="pipeline" className="scroll-mt-28">
            <div className="max-w-[68ch]"><p className="eyebrow">Signal pipeline</p><h2 className="section-heading mt-3">Seven signals, one calibrated result.</h2><p className="mt-4 leading-7 text-muted-foreground">Each stage contributes a bounded piece of evidence. Fusion combines those signals into the score; calibration turns measured residual error into an interval.</p></div>
            <div className="mt-7"><PipelineDiagram/></div>
          </section>

          <div className="mt-14 grid gap-10 md:grid-cols-2">
            <MethodSection id="uncertainty" icon={<ShieldCheck className="size-5" strokeWidth={1.5}/>} title="Honest uncertainty">
              <p>Split-conformal calibration targets 90% coverage of held-out reference labels. An interval describes empirical coverage across comparable examples, not the probability that one prediction is correct.</p>
            </MethodSection>
            <MethodSection id="rankings" icon={<Scale className="size-5" strokeWidth={1.5}/>} title="Fair rankings">
              <p>Empirical Bayes shrinkage moves a product&apos;s trust-weighted mean toward the population mean in proportion to uncertainty. Small or inconsistent review sets cannot dominate through a fragile average.</p>
            </MethodSection>
          </div>

          <MethodSection id="labels" icon={<Tags className="size-5" strokeWidth={1.5}/>} title="Labels and validation">
            <p>Round 1 uses 1,059 labeled reviews across 878 products, produced by consensus of two LLM labelers. The reference annotations used for agreement were produced by Claude, an LLM, not by humans. Agreement therefore measures consistency with an LLM reference, not human validation.</p>
          </MethodSection>

          <section id="benchmarks" className="mt-14 scroll-mt-28 border-t border-border pt-10">
            <div className="max-w-[68ch]"><p className="eyebrow">Benchmarks</p><h2 className="section-heading mt-3">Measured, not implied.</h2><p className="mt-4 leading-7 text-muted-foreground">Every displayed value comes from completed reports. No production metric is inferred from UI behavior.</p></div>
            {benchmarkRounds.map((round) => <div key={round.round} className="mt-8"><p className="text-sm font-medium text-muted-foreground">{round.label}</p>{round.status === "complete" ? <BenchmarkResults round={round}/> : <div className="mt-4 border-l-2 border-primary bg-muted/35 p-5"><p className="font-heading text-xl font-semibold">Evaluation in progress</p><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Round 2 has no published metrics yet. Results will appear only after the required evaluation reports are complete and accepted.</p></div>}</div>)}
          </section>

          <section id="limitations" className="mt-14 scroll-mt-28 border-t border-border pt-10">
            <div className="flex items-center gap-2 text-primary"><CircleHelp className="size-5" strokeWidth={1.5}/><span className="eyebrow">Read with care</span></div>
            <h2 className="section-heading mt-3">Limitations</h2>
            <ul className="mt-6 grid gap-px overflow-hidden rounded-card border border-border bg-border sm:grid-cols-2">
              <li className="bg-card p-5 leading-7 text-muted-foreground"><strong className="block text-foreground">No established ground truth</strong>“Experience” is a modeled target based on LLM-generated labels.</li>
              <li className="bg-card p-5 leading-7 text-muted-foreground"><strong className="block text-foreground">A narrow domain</strong>Models are trained on English Amazon earbud reviews. Other languages and categories are flagged, not reliably scored.</li>
              <li className="bg-card p-5 leading-7 text-muted-foreground"><strong className="block text-foreground">Not fraud detection</strong>Review quality is a weighting signal. It does not verify purchases or prove authenticity.</li>
              <li className="bg-card p-5 leading-7 text-muted-foreground"><strong className="block text-foreground">Intervals are empirical</strong>Coverage on a test set does not guarantee coverage for every future input or distribution shift.</li>
            </ul>
          </section>

          <div className="mt-12 border-t border-border pt-8"><Button asChild size="lg"><Link href="/">Analyze a review<ArrowRight/></Link></Button></div>
        </article>
      </div>
    </>
  )
}
