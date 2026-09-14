"use client"

import { motion, useReducedMotion } from "motion/react"
import { usePathname } from "next/navigation"

import { EASE_OUT, motionDuration } from "@/lib/motion"

export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const reduced = useReducedMotion()

  return (
    <motion.div
      key={pathname}
      initial={{ opacity: 0, y: reduced ? 0 : 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduced ? motionDuration.hover : motionDuration.ui, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  )
}
