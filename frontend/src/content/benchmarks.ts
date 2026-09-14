// Update from reports/ after each training round.
export const roundOne = {
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
} as const
