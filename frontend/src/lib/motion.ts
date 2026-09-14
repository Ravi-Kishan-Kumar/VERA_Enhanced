import type { Transition } from "motion/react"

export const motionDuration = {
  hover: 0.12,
  ui: 0.2,
  panel: 0.32,
  score: 0.6,
  count: 1.2,
} as const

export const EASE_OUT = [0.22, 1, 0.36, 1] as const

export const UI_SPRING: Transition = {
  type: "spring",
  stiffness: 420,
  damping: 36,
  mass: 0.9,
}

export const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0 },
} as const
