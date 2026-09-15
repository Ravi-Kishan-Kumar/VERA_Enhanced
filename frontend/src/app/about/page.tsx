import { ArrowRight, CircleHelp, Scale, ShieldCheck, Tags } from "lucide-react"
import Link from "next/link"

import { Button } from "@/components/ui/button"
import { PipelineDiagram } from "@/components/vera/pipeline-diagram"
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

function MeasureBar({ label, vera, baseline }: { label: string; vera: number; baseline: number }) {
  return <div className="grid gap-2"><div className="flex items-center justify-between gap-4 text-xs"><span>{label}</span><span className="font-mono text-muted-foreground">Lower is better</span></div><div className="grid gap-1.5"><div className="flex items-center gap-2"><span className="w-14 text-xs text-muted-foreground">VERA</span><span className="h-2 rounded-full bg-primary" style={{ width: `${(vera / baseline) * 75}%` }}/><strong className="font-mono text-xs">{vera.toFixed(3)}</strong></div><div className="flex items-center gap-2"><span className="w-14 text-xs text-muted-foreground">Stars</span><span className="h-2 rounded-full bg-muted-foreground/35" style={{ width: "75%" }}/><strong className="font-mono text-xs">{baseline.toFixed(3)}</strong></div></div></div>
}

function BenchmarkResults({ round }: { round: CompletedBenchmarkRound }) {
  const rows = [
    { label: "15-fold grouped CV MAE", vera: `${round.crossValidation.veraMae} ± ${round.crossValidation.veraStd}`, reference: `Stars ${round.crossValidation.starsMae} ± ${round.crossValidation.starsStd}` },
    { label: "Held-out test MAE", vera: String(round.heldOut.veraMae), reference: `Stars ${round.heldOut.starsMae}` },
    { label: "90% interval coverage", vera: `${round.coverage.value}%`, reference: `n = ${round.coverage.reviews}` },
    { label: "Label agreement κ", vera: String(round.agreement.selfKappa), reference: `LLM ref. ${round.agreement.referenceLlmKappa.toFixed(3)}` },
    { label: "Median CPU latency", vera: `≈ ${round.latency.medianCpuSeconds}s`, reference: `max ${round.latency.maxCpuSeconds}s / ${round.latency.reviews}` },
  ]

  return (
    <div className="mt-8 grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
      <div className="overflow-hidden rounded-card border border-border bg-card">
        <dl className="divide-y divide-border sm:hidden">
          {rows.map((row) => <div key={row.label} className="grid gap-3 p-4"><dt className="text-sm font-medium">{row.label}</dt><dd className="grid grid-cols-2 gap-3"><span><span className="block text-[11px] uppercase tracking-wider text-muted-foreground">VERA</span><span className="metric-number mt-1 block text-sm font-semibold">{row.vera}</span></span><span><span className="block text-[11px] uppercase tracking-wider text-muted-foreground">Reference</span><span className="metric-number mt-1 block text-sm text-muted-foreground">{row.reference}</span></span></dd></div>)}
        </dl>
        <table className="hidden w-full text-left text-sm sm:table">
          <caption className="sr-only">{round.label} benchmark measurements</caption>
          <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground"><tr><th className="px-4 py-3 font-medium">Measure</th><th className="px-4 py-3 text-right font-medium">VERA</th><th className="px-4 py-3 text-right font-medium">Reference</th></tr></thead>
          <tbody className="divide-y divide-border">{rows.map((row) => <tr key={row.label}><td className="px-4 py-3">{row.label}</td><td className="metric-number px-4 py-3 text-right">{row.vera}</td><td className="metric-number px-4 py-3 text-right text-muted-foreground">{row.reference}</td></tr>)}</tbody>
        </table>
      </div>
      <div className="rounded-card border border-border bg-card p-5"><h3 className="text-sm font-semibold">Prediction error</h3><div className="mt-7 grid gap-8"><MeasureBar label="Grouped cross-validation" vera={round.crossValidation.veraMae} baseline={round.crossValidation.starsMae}/><MeasureBar label="Held-out test" vera={round.heldOut.veraMae} baseline={round.heldOut.starsMae}/></div><div className="mt-7 border-t border-border pt-4 text-xs leading-5 text-muted-foreground"><p>VERA won {round.crossValidation.foldsWon} folds.</p><p>Wilcoxon p = {round.crossValidation.wilcoxon}.</p></div></div>
    </div>
  )
}

export default function AboutPage() {
  return (
    <>
      <header className="page-hero"><div className="font-mono text-xs uppercase tracking-[0.16em] text-primary">Methodology</div><h1 className="display-title mt-5 max-w-5xl">How VERA reads a review.</h1><p className="mt-6 max-w-3xl text-pretty text-base leading-7 text-muted-foreground sm:text-lg">A star rating is one click. VERA estimates the experience described by the text, then makes the uncertainty and limitations visible.</p></header>
      <div className="grid items-start gap-12 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <nav aria-label="On this page" className="sticky top-24 hidden rounded-xl border border-border bg-card p-3 lg:block"><p className="px-2 py-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">On this page</p>{toc.map(([href, label]) => <a key={href} href={`#${href}`} className="block min-h-10 rounded-lg px-2 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground">{label}</a>)}</nav>
        <article className="min-w-0 space-y-[var(--space-section)] pb-10">
          <section id="pipeline" className="scroll-mt-28"><div className="max-w-[68ch]"><span className="font-mono text-xs text-primary">01</span><h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em]">Seven signals, one calibrated result.</h2><p className="mt-4 leading-7 text-muted-foreground">Each stage contributes a bounded piece of evidence. Fusion combines those signals into the score; calibration turns measured residual error into an interval.</p></div><div className="mt-8"><PipelineDiagram/></div></section>
          <section id="uncertainty" className="scroll-mt-28 max-w-[68ch]"><div className="flex items-center gap-3"><ShieldCheck className="size-5 text-primary" strokeWidth={1.5}/><span className="font-mono text-xs text-primary">02</span></div><h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em]">Honest uncertainty</h2><p className="mt-4 leading-7 text-muted-foreground">Split-conformal calibration targets 90% coverage of held-out reference labels. The measured Round 1 coverage is shown below. An interval does not mean a single prediction has a 90% probability of being correct; it describes empirical coverage across comparable examples.</p></section>
          <section id="rankings" className="scroll-mt-28 max-w-[68ch]"><div className="flex items-center gap-3"><Scale className="size-5 text-primary" strokeWidth={1.5}/><span className="font-mono text-xs text-primary">03</span></div><h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em]">Fair rankings</h2><p className="mt-4 leading-7 text-muted-foreground">Product scores use Empirical Bayes shrinkage. A product&apos;s trust-weighted mean moves toward the population mean in proportion to uncertainty, so a small or inconsistent review set cannot dominate through a fragile average.</p></section>
          <section id="labels" className="scroll-mt-28 max-w-[68ch]"><div className="flex items-center gap-3"><Tags className="size-5 text-primary" strokeWidth={1.5}/><span className="font-mono text-xs text-primary">04</span></div><h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em]">Labels and validation</h2><p className="mt-4 leading-7 text-muted-foreground">Round 1 uses 1,059 labeled reviews across 878 products, produced by consensus of two LLM labelers. The reference annotations used for agreement were produced by Claude, an LLM — not by humans. Agreement therefore measures consistency with an LLM reference, not human validation.</p></section>
          <section id="benchmarks" className="scroll-mt-28"><div className="max-w-[68ch]"><span className="font-mono text-xs text-primary">05</span><h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em]">Measured benchmarks</h2><p className="mt-4 leading-7 text-muted-foreground">Every displayed value comes from completed reports. No production metric is inferred from UI behavior.</p></div>
            {benchmarkRounds.map((round) => <div key={round.round} className="mt-8"><p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">{round.label}</p>{round.status === "complete" ? <BenchmarkResults round={round}/> : <div className="mt-4 rounded-card border border-dashed border-border bg-card/55 p-6"><p className="text-lg font-semibold">Evaluation in progress</p><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Round 2 has no published metrics yet. Results will appear only after the required evaluation reports are complete and accepted.</p></div>}</div>)}
          </section>
          <section id="limitations" className="scroll-mt-28 rounded-card border border-border bg-card p-6 sm:p-8"><div className="flex items-center gap-3"><CircleHelp className="size-5 text-primary" strokeWidth={1.5}/><span className="font-mono text-xs text-primary">06</span></div><h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em]">Limitations</h2><ul className="mt-5 grid gap-4 leading-7 text-muted-foreground"><li><strong className="text-foreground">No established ground truth.</strong> “Experience” is a modeled target based on LLM-generated labels.</li><li><strong className="text-foreground">A narrow domain.</strong> Models are trained on English Amazon earbud reviews; other languages and product categories are flagged, not reliably scored.</li><li><strong className="text-foreground">Not fraud detection.</strong> Review quality is a weighting signal. It does not verify purchases or prove authenticity.</li><li><strong className="text-foreground">Intervals are empirical.</strong> Coverage observed on a test set does not guarantee coverage for every future input or distribution shift.</li></ul></section>
          <div className="border-t border-border pt-8"><Button asChild size="lg"><Link href="/">Analyze a review<ArrowRight/></Link></Button></div>
        </article>
      </div>
    </>
  )
}
