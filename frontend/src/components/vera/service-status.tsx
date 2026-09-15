"use client"

import { LoaderCircle, RotateCcw } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"

export function ServiceStatus() {
  const [state, setState] = useState<"checking" | "ready" | "unavailable">("checking")
  const [hasFailed, setHasFailed] = useState(false)
  const controller = useRef<AbortController | null>(null)

  async function check() {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    setState("checking")
    try { await api("/ready", { signal: current.signal }); if (!current.signal.aborted) setState("ready") } catch { if (!current.signal.aborted) { setHasFailed(true); setState("unavailable") } }
  }

  useEffect(() => {
    const current = new AbortController()
    controller.current = current
    api("/ready", { signal: current.signal }).then(() => { if (!current.signal.aborted) setState("ready") }).catch(() => { if (!current.signal.aborted) { setHasFailed(true); setState("unavailable") } })
    return () => current.abort()
  }, [])

  if (state === "ready" || (state === "checking" && !hasFailed)) return null
  return <aside className="mt-5 flex flex-col items-stretch gap-2 rounded-card border border-amber-700/20 bg-amber-500/8 px-4 py-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between" aria-label="Service availability"><div role="status" className="flex items-start gap-2 sm:items-center">{state === "checking" ? <LoaderCircle className="mt-0.5 size-4 shrink-0 animate-spin text-amber-700 motion-reduce:animate-none sm:mt-0 dark:text-amber-300"/> : <span className="mt-1.5 size-2 shrink-0 rounded-full bg-amber-700 sm:mt-0 dark:bg-amber-300" aria-hidden="true"/>}{state === "checking" ? "Checking database availability" : "The API database is temporarily unavailable. Your draft is safe; retry before submitting."}</div>{state === "unavailable" && <Button type="button" variant="ghost" size="sm" className="self-end sm:self-auto" onClick={check}><RotateCcw/>Retry connection</Button>}</aside>
}
