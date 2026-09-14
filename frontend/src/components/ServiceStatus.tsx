"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

/** One readiness check per mount, then manual retries only. Never submits a review. */
export function ServiceStatus() {
  const [state, setState] = useState<"checking" | "ready" | "unavailable">("checking");
  const [hasFailed, setHasFailed] = useState(false);
  const controller = useRef<AbortController | null>(null);

  async function check() {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setState("checking");
    try {
      await api("/ready", { signal: current.signal });
      if (!current.signal.aborted) setState("ready");
    } catch {
      if (!current.signal.aborted) { setHasFailed(true); setState("unavailable"); }
    }
  }

  useEffect(() => {
    const current = new AbortController();
    controller.current = current;
    api("/ready", { signal: current.signal })
      .then(() => { if (!current.signal.aborted) setState("ready"); })
      .catch(() => { if (!current.signal.aborted) { setHasFailed(true); setState("unavailable"); } });
    return () => controller.current?.abort();
  }, []);

  // A successful initial check must not shift the entire page after hydration.
  if (state === "ready" || (state === "checking" && !hasFailed)) return null;
  return <aside className={`service-status ${state === "unavailable" ? "service-unavailable" : ""}`} aria-label="Service availability">
    <div role="status"><span className="availability-dot" aria-hidden="true"/>{state === "checking" ? "Checking service availability…" : "The service is temporarily unavailable. You can keep writing; retry before submitting."}</div>
    {state === "unavailable" && <button className="text-button" type="button" onClick={check}>Retry connection <span aria-hidden="true">↻</span></button>}
  </aside>;
}
