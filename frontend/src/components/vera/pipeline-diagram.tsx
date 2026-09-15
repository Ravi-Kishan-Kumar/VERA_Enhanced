"use client"

import { ArrowRight } from "lucide-react"

import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"

const agents = [
  { name: "Preprocess", detail: "Cleans text, checks language, and flags out-of-domain input." },
  { name: "Experience", detail: "Estimates the experience described by the review text." },
  { name: "Aspects", detail: "Finds evidence across ten earbud-specific aspects and their sentiment." },
  { name: "Consistency", detail: "Measures the gap between the submitted stars and text evidence." },
  { name: "Quality", detail: "Weights review metadata without claiming authenticity or purchase proof." },
  { name: "Domain", detail: "Adds rating-pattern signals learned from the earbud review domain." },
  { name: "Fusion", detail: "Combines every signal, then calibrates the corrected score and interval." },
] as const

export function PipelineDiagram() {
  return (
    <div className="rounded-card border border-border bg-card p-4 sm:p-5">
      <ol className="grid overflow-hidden rounded-control border border-border bg-border lg:grid-cols-7">
        {agents.map((agent, index) => (
          <li key={agent.name} className="relative bg-card not-last:border-b not-last:border-border lg:not-last:border-r lg:not-last:border-b-0">
            <HoverCard openDelay={120} closeDelay={80}>
              <HoverCardTrigger asChild>
                <button type="button" className="flex min-h-14 w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-medium transition-colors duration-150 hover:bg-muted focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring lg:min-h-24 lg:flex-col lg:justify-center lg:px-2 lg:text-center">
                  <span>{agent.name}</span>
                  {index < agents.length - 1 && <ArrowRight className="size-3.5 shrink-0 text-primary lg:absolute lg:-right-2 lg:z-10 lg:rounded-full lg:bg-card" strokeWidth={1.5} aria-hidden="true"/>}
                </button>
              </HoverCardTrigger>
              <HoverCardContent side="top" className="w-64">
                <p className="font-heading text-lg font-semibold">{agent.name}</p>
                <p className="mt-1 text-sm leading-5 text-muted-foreground">{agent.detail}</p>
              </HoverCardContent>
            </HoverCard>
          </li>
        ))}
      </ol>
      <p className="mt-4 text-xs leading-5 text-muted-foreground">Focus or hover a stage for its role. The sequence describes inference order, not private reasoning.</p>
    </div>
  )
}
