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
  return <aside className="fixed inset-x-4 top-20 z-30 mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-2 rounded-xl border border-white/60 bg-white/85 px-3 py-2 text-sm text-muted-foreground shadow-lg backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/85" aria-label="Service availability"><div role="status" className="flex items-center gap-2">{state === "checking" ? <LoaderCircle className="size-4 animate-spin text-amber-600 motion-reduce:animate-none"/> : <span className="size-2 rounded-full bg-amber-600" aria-hidden="true"/>}{state === "checking" ? "Checking service availability" : "The service is temporarily unavailable. You can keep writing; retry before submitting."}</div>{state === "unavailable" && <Button type="button" variant="ghost" size="sm" onClick={check}><RotateCcw/>Retry connection</Button>}</aside>
}
