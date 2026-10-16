import { InsightsHub } from "@/components/vera/insights-hub"
import { pageMetadata } from "@/lib/metadata"

export const metadata = pageMetadata(
  "Insights & Comparative Study",
  "Earbuds vs. Headphones study, Amazon rating inflation analysis across 5,196+ reviews, and 7-agent ML performance.",
  "/insights"
)

export default function InsightsPage() {
  return (
    <>
      <header className="page-hero grid items-end gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.6fr)]">
        <div>
          <p className="eyebrow">Deep Analysis &amp; Research</p>
          <h1 className="display-title mt-3 max-w-4xl">Insights &amp; Comparative Study</h1>
        </div>
        <p className="max-w-xl text-base leading-7 text-muted-foreground">
          Explore the cross-category Earbuds vs. Headphones study, empirical rating inflation analysis, and 7-agent ML architecture metrics.
        </p>
      </header>
      <InsightsHub />
    </>
  )
}
