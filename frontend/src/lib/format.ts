import { score } from "@/lib/types"

export function displayScore(value: number | null | undefined) {
  return value == null ? "N/A" : score(value)
}
