import type { SVGProps } from "react"

import { cn } from "@/lib/utils"

interface DotPatternProps extends SVGProps<SVGSVGElement> {
  width?: number
  height?: number
  cx?: number
  cy?: number
  cr?: number
}

/** Static, presentation-only dot field. It never starts a background animation. */
export function DotPattern({
  width = 24,
  height = 24,
  cx = 1,
  cy = 1,
  cr = 1,
  className,
  ...props
}: DotPatternProps) {
  return (
    <svg
      aria-hidden="true"
      className={cn("pointer-events-none absolute inset-0 size-full", className)}
      {...props}
    >
      <defs>
        <pattern id="vera-dot-field" width={width} height={height} patternUnits="userSpaceOnUse">
          <circle cx={cx} cy={cy} r={cr} fill="currentColor" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#vera-dot-field)" />
    </svg>
  )
}
