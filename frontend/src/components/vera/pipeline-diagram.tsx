"use client"

import { motion, useInView, useReducedMotion } from "motion/react"
import { useRef } from "react"

import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"
import { EASE_OUT } from "@/lib/motion"

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
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: "-80px" })
  const reduced = useReducedMotion()

  return (
    <div ref={ref} className="relative rounded-card border border-border bg-card p-5 sm:p-7">
      <svg viewBox="0 0 1000 20" preserveAspectRatio="none" className="absolute left-[7%] top-[3.4rem] hidden h-5 w-[86%] lg:block" aria-hidden="true"><path d="M 0 10 L 1000 10" stroke="var(--border)" strokeWidth="3"/><motion.path d="M 0 10 L 1000 10" stroke="var(--primary)" strokeWidth="3" initial={{ pathLength: 0 }} animate={{ pathLength: inView ? 1 : 0 }} transition={{ duration: reduced ? 0 : 0.8, ease: EASE_OUT }}/></svg>
      <ol className="relative grid gap-2 before:absolute before:bottom-5 before:left-5 before:top-5 before:w-px before:bg-border lg:grid-cols-7 lg:gap-3 lg:before:hidden">
        {agents.map((agent, index) => <li key={agent.name} className="relative z-10"><HoverCard openDelay={120} closeDelay={80}><HoverCardTrigger asChild><button type="button" className="group flex min-h-14 w-full items-center gap-3 rounded-xl border border-border bg-background p-2.5 text-left transition-colors duration-150 hover:border-primary/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:min-h-24 lg:flex-col lg:justify-center lg:text-center"><span className="grid size-8 shrink-0 place-items-center rounded-lg border border-primary/25 bg-primary/8 font-mono text-xs font-semibold text-primary">{String(index + 1).padStart(2, "0")}</span><span className="text-xs font-medium">{agent.name}</span></button></HoverCardTrigger><HoverCardContent side="top" className="w-64"><p className="text-sm font-semibold">{agent.name} agent</p><p className="mt-1 text-sm leading-5 text-muted-foreground">{agent.detail}</p></HoverCardContent></HoverCard></li>)}
      </ol>
      <p className="mt-5 text-xs leading-5 text-muted-foreground">Focus or hover any node for its role. The diagram describes inference order; it does not expose private chain-of-thought.</p>
    </div>
  )
}
