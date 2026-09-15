"use client"

import dynamic from "next/dynamic"

import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ASPECTS, aspectName, type Aspect, type AspectKey, type AspectSummary, type Sentiment } from "@/lib/types"
import { cn } from "@/lib/utils"
import type { AspectChartRow } from "@/components/vera/aspect-radar-chart"

const AspectRadarChart = dynamic(() => import("@/components/vera/aspect-radar-chart"), {
  ssr: false,
  loading: () => <Skeleton className="mx-auto aspect-square max-h-[310px] w-full rounded-xl" />,
})

const sentimentStyle: Record<Sentiment, string> = {
  positive: "bg-emerald-600 dark:bg-emerald-400",
  negative: "bg-red-600 dark:bg-red-400",
  neutral: "bg-slate-500 dark:bg-slate-400",
  not_mentioned: "bg-muted-foreground/25",
}

export function AspectBreakdown({ aspects, summary }: { aspects?: Partial<Record<AspectKey, Aspect>> | null; summary?: Partial<Record<AspectKey, AspectSummary>> | null }) {
  const rows = ASPECTS.map((key) => {
    const aggregate = summary?.[key]
    const aspect = aspects?.[key]
    const detected = aggregate ? aggregate.mention_count > 0 : Boolean(aspect?.detected)
    const sentiment: Sentiment = detected ? aggregate?.dominant_sentiment || aspect?.sentiment || "neutral" : "not_mentioned"
    const raw = aggregate ? aggregate.net_sentiment : sentiment === "positive" ? 1 : sentiment === "negative" ? -1 : 0
    return { key, label: aspectName(key), detected, sentiment, raw, value: raw + 1, mentions: aggregate?.mention_count }
  })
  const detected = rows.filter((row) => row.detected)
  const chartRows: AspectChartRow[] = detected.map(({ key, label, value }) => ({ key, label, value }))

  return (
    <section className="rounded-card border border-border bg-card p-5 sm:p-6" aria-labelledby="aspect-title">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><span className="font-mono text-xs uppercase tracking-[0.12em] text-muted-foreground">Aspect evidence</span><h2 id="aspect-title" className="mt-2 text-xl font-semibold tracking-[-0.025em]">What the review{summary ? "s reveal" : " reveals"}</h2></div><span className="font-mono text-xs text-muted-foreground">{detected.length} / 10 detected</span></div>
      {detected.length === 0 ? (
        <div className="mt-5 rounded-xl border border-dashed border-border bg-muted/35 p-5">
          <p className="text-sm font-medium">No aspect evidence detected</p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">This result did not identify a specific product aspect. VERA does not display unmentioned categories as evidence.</p>
        </div>
      ) : <Tabs defaultValue={detected.length >= 3 ? "radar" : "bars"} className="mt-5">
        <TabsList aria-label="Aspect visualization" className="h-10"><TabsTrigger value="radar" className="min-h-9 px-3" disabled={detected.length < 3}>Radar</TabsTrigger><TabsTrigger value="bars" className="min-h-9 px-3">Bars</TabsTrigger></TabsList>
        <TabsContent value="radar" className="pt-5">
          {detected.length >= 3 ? <><AspectRadarChart data={chartRows}/><p className="text-center text-xs text-muted-foreground">Center is negative; middle is neutral; edge is positive. Only detected aspects are plotted.</p></> : <p className="rounded-xl bg-muted p-6 text-sm text-muted-foreground">A radar needs at least three detected aspects. Use the bar view for the available evidence.</p>}
        </TabsContent>
        <TabsContent value="bars" className="pt-5">
          <ul className="grid gap-3" aria-label="Aspect sentiment values">
            {detected.map((row) => <li key={row.key} className="grid grid-cols-[minmax(7rem,0.8fr)_1fr_auto] items-center gap-3 text-sm"><span>{row.label}</span><span className="relative h-2 overflow-hidden rounded-full bg-muted"><span className={cn("absolute inset-y-0 left-0 rounded-full", sentimentStyle[row.sentiment])} style={{ width: `${Math.max(8, ((row.raw + 1) / 2) * 100)}%` }}/></span><span className="min-w-20 text-right text-xs capitalize text-muted-foreground">{row.sentiment}{row.mentions != null ? ` · ${row.mentions}` : ""}</span></li>)}
          </ul>
        </TabsContent>
      </Tabs>}
    </section>
  )
}
