"use client"

import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart } from "recharts"

import { ChartContainer, type ChartConfig } from "@/components/ui/chart"

export type AspectChartRow = { key: string; label: string; value: number }

const config = { sentiment: { label: "Sentiment", color: "var(--primary)" } } satisfies ChartConfig

export default function AspectRadarChart({ data }: { data: AspectChartRow[] }) {
  return (
    <ChartContainer config={config} className="mx-auto aspect-square max-h-[310px] w-full" initialDimension={{ width: 310, height: 310 }} aria-hidden="true">
      <RadarChart data={data} outerRadius="65%">
        <PolarGrid stroke="var(--border)" />
        <PolarAngleAxis dataKey="label" tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} />
        <PolarRadiusAxis domain={[0, 2]} tickCount={3} tick={false} axisLine={false} />
        <Radar name="Sentiment" dataKey="value" stroke="var(--primary)" fill="var(--primary)" fillOpacity={0.12} isAnimationActive={false} />
      </RadarChart>
    </ChartContainer>
  )
}

