import { Suspense } from "react"

import { Skeleton } from "@/components/ui/skeleton"
import { CompareView } from "@/components/vera/compare-view"
import { pageMetadata } from "@/lib/metadata"

export const metadata = pageMetadata(
  "Product Comparison Arena",
  "Head-to-head aspect showdown, delta scoring, and AI verdicts comparing earbuds and headphones.",
  "/compare"
)

export default function ComparePage() {
  return (
    <>
      <header className="page-hero grid items-end gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.6fr)]">
        <div>
          <p className="eyebrow">Head-to-Head Arena</p>
          <h1 className="display-title mt-3 max-w-4xl">Product Comparison</h1>
        </div>
        <p className="max-w-xl text-base leading-7 text-muted-foreground">
          Aspect-by-aspect showdown with delta scores, star inflation comparisons, and calibrated verdicts between any two devices.
        </p>
      </header>
      <Suspense fallback={<Skeleton className="h-96 w-full rounded-2xl" />}>
        <CompareView />
      </Suspense>
    </>
  )
}
