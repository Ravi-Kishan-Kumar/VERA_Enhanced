"use client"

import { Star } from "lucide-react"

import { cn } from "@/lib/utils"

export function StarRating({ value, onChange, disabled = false }: { value: number; onChange: (value: number) => void; disabled?: boolean }) {
  const percentage = (value / 5) * 100

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-4">
        <div className="relative" aria-hidden="true">
          <div className="flex gap-1 text-muted-foreground/35">
            {Array.from({ length: 5 }, (_, index) => <Star key={index} className="size-6" strokeWidth={1.5} />)}
          </div>
          <div className="absolute inset-y-0 left-0 overflow-hidden text-primary" style={{ width: `${percentage}%` }}>
            <div className="flex w-max gap-1">
              {Array.from({ length: 5 }, (_, index) => <Star key={index} className="size-6 fill-current" strokeWidth={1.5} />)}
            </div>
          </div>
        </div>
        <output htmlFor="star-rating" className="min-w-12 rounded-lg border border-border bg-muted/50 px-2 py-1 text-center font-mono text-sm tabular-nums">{value.toFixed(1)}</output>
      </div>
      <input
        id="star-rating"
        name="star_rating"
        type="range"
        min={1}
        max={5}
        step={0.5}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        aria-label="Original star rating, from 1 to 5 in half-star steps"
        aria-valuetext={`${value.toFixed(1)} out of 5 stars`}
        className={cn("h-11 w-full cursor-pointer accent-primary", disabled && "cursor-not-allowed opacity-60")}
      />
      <div aria-hidden="true" className="flex justify-between font-mono text-[11px] text-muted-foreground"><span>1.0</span><span>Half-star steps</span><span>5.0</span></div>
    </div>
  )
}
