"use client"

import { ErrorState } from "@/components/vera/states"

export default function ErrorPage({ reset }: { reset: () => void }) {
  return <ErrorState message="This page encountered an unexpected error. A submitted review may still be processing." retry={reset}/>
}
