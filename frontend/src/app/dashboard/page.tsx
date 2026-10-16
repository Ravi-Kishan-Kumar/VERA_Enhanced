import { DashboardView } from "@/components/vera/dashboard-view"
import { pageMetadata } from "@/lib/metadata"

export const metadata = pageMetadata(
  "Model & Agent Dashboard",
  "Live telemetry, 7-agent signal performance, aspect sentiment landscape, and ML gate verifications.",
  "/dashboard"
)

export default function DashboardPage() {
  return (
    <>
      <header className="page-hero grid items-end gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.6fr)]">
        <div>
          <p className="eyebrow">System Telemetry &amp; ML Governance</p>
          <h1 className="display-title mt-3 max-w-4xl">Model &amp; Agent Performance</h1>
        </div>
        <p className="max-w-xl text-base leading-7 text-muted-foreground">
          Real-time signal analytics across all 7 agents, empirical conformal coverage, rating inflation indices, and gate evaluations.
        </p>
      </header>
      <DashboardView />
    </>
  )
}
