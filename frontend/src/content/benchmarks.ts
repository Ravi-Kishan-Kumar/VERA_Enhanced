export type CompletedBenchmarkRound = {
  readonly status: "complete"
  readonly round: number
  readonly label: string
  readonly labels: number
  readonly products: number
  readonly labelSource: string
  readonly crossValidation: {
    readonly veraMae: number; readonly veraStd: number; readonly starsMae: number; readonly starsStd: number
    readonly foldsWon: string; readonly wilcoxon: string
  }
  readonly heldOut: { readonly veraMae: number; readonly starsMae: number }
  readonly coverage: { readonly value: number; readonly reviews: number }
  readonly agreement: { readonly selfKappa: number; readonly referenceLlmKappa: number }
  readonly latency: { readonly medianCpuSeconds: number; readonly maxCpuSeconds: number; readonly reviews: number }
}

export type PendingBenchmarkRound = {
  readonly status: "pending"
  readonly round: number
  readonly label: string
  readonly reportFiles: readonly string[]
}

export type BenchmarkRound = CompletedBenchmarkRound | PendingBenchmarkRound

// Round 1 values are copied only from the report-backed figures approved in the UI brief.
export const roundOne = {
  status: "complete",
  round: 1,
  label: "Round 1 · 1,059 labels",
  labels: 1_059,
  products: 878,
  labelSource: "Consensus of two LLM labelers",
  crossValidation: {
    veraMae: 0.307,
    veraStd: 0.015,
    starsMae: 0.465,
    starsStd: 0.022,
    foldsWon: "15/15",
    wilcoxon: "3.1e-5",
  },
  heldOut: { veraMae: 0.315, starsMae: 0.501 },
  coverage: { value: 93.5, reviews: 214 },
  agreement: { selfKappa: 0.979, referenceLlmKappa: 0.95 },
  latency: { medianCpuSeconds: 1.5, maxCpuSeconds: 6.7, reviews: 10 },
} as const satisfies CompletedBenchmarkRound

export const roundTwo = {
  status: "pending",
  round: 2,
  label: "Round 2",
  // TODO: populate only after evaluation_report.json, cv_comparison.json,
  // aspect_detector.json, and calibration.json contain accepted Round 2 results.
  reportFiles: ["evaluation_report.json", "cv_comparison.json", "aspect_detector.json", "calibration.json"],
} as const satisfies PendingBenchmarkRound

export const benchmarkRounds = [roundOne, roundTwo] as const satisfies readonly BenchmarkRound[]
