"use client"

import { useEffect, useRef, type ComponentPropsWithoutRef } from "react"

import { cn } from "@/lib/utils"

interface NumberTickerProps extends ComponentPropsWithoutRef<"span"> {
  value: number
  startValue?: number
  delay?: number
  decimalPlaces?: number
}

export function NumberTicker({ value, startValue = 0, delay = 0, className, decimalPlaces = 0, ...props }: NumberTickerProps) {
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const element = ref.current
    if (!element || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
    const duration = 800
    let frame = 0
    let started = 0
    const timeout = window.setTimeout(() => {
      const tick = (time: number) => {
        if (!started) started = time
        const progress = Math.min(1, (time - started) / duration)
        const eased = 1 - Math.pow(1 - progress, 3)
        const current = startValue + (value - startValue) * eased
        element.textContent = current.toFixed(decimalPlaces)
        if (progress < 1) frame = window.requestAnimationFrame(tick)
      }
      frame = window.requestAnimationFrame(tick)
    }, delay * 1_000)
    return () => { window.clearTimeout(timeout); window.cancelAnimationFrame(frame) }
  }, [decimalPlaces, delay, startValue, value])

  return <span ref={ref} className={cn("inline-block tabular-nums", className)} {...props}>{value.toFixed(decimalPlaces)}</span>
}
