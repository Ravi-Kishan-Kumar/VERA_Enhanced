"use client"

import {
  ArrowRight,
  Award,
  CheckCircle2,
  ExternalLink,
  Globe,
  Headphones,
  Scale,
  Search,
  Sparkles,
  Star,
  Trophy,
  XCircle,
  Zap,
} from "lucide-react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import type { WebCompareResponse } from "@/lib/types"
import { cn } from "@/lib/utils"

const POPULAR_MATCHUPS = [
  {
    title: "🎧 Over-Ear ANC Titans",
    prodA: "Sony WH-1000XM5",
    prodB: "Bose QuietComfort 45",
    desc: "Sony WH-1000XM5 vs. Bose QC 45",
  },
  {
    title: "👑 Flagship TWS Battle",
    prodA: "Apple AirPods Pro (2nd Generation, USB-C)",
    prodB: "Sony WF-1000XM5 Wireless Earbuds",
    desc: "AirPods Pro 2 vs. Sony WF-1000XM5",
  },
  {
    title: "⚖️ Cross-Category Showdown",
    prodA: "Sony WH-1000XM5",
    prodB: "Apple AirPods Pro (2nd Generation, USB-C)",
    desc: "Over-Ear Headphones vs. In-Ear Flagship Earbuds",
  },
  {
    title: "💰 Value King vs. Budget Best-Seller",
    prodA: "OnePlus Buds 3",
    prodB: "boAt Airdopes 141",
    desc: "OnePlus Buds 3 (₹5,499) vs. boAt Airdopes 141 (₹1,299)",
  },
]

const QUICK_SUGGESTIONS = [
  "Sony WH-1000XM5",
  "Bose QuietComfort 45",
  "Apple AirPods Pro (2nd Generation, USB-C)",
  "OnePlus Buds 3",
  "Sennheiser Momentum 4",
  "Sony WH-CH720N",
  "Realme Buds Air 6 Pro",
  "boAt Airdopes 141",
]

export function CompareView() {
  const searchParams = useSearchParams()
  const initialA = searchParams.get("product_a") || searchParams.get("a") || "Sony WH-1000XM5"
  const initialB = searchParams.get("product_b") || searchParams.get("b") || "Bose QuietComfort 45"

  const [productA, setProductA] = useState(initialA)
  const [productB, setProductB] = useState(initialB)
  const [result, setResult] = useState<WebCompareResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const executeCompare = async (a: string, b: string) => {
    if (!a.trim() || !b.trim()) {
      toast.error("Please provide both product names to compare.")
      return
    }
    setLoading(true)
    try {
      const res = await api<WebCompareResponse>("/compare/web", {
        method: "POST",
        body: JSON.stringify({ product_a: a.trim(), product_b: b.trim() }),
      })
      setResult(res)
    } catch (err) {
      toast.error("Failed to compare products from live web data.")
    } finally {
      setLoading(false)
    }
  }

  // Load initial comparison on mount
  useEffect(() => {
    executeCompare(initialA, initialB)
  }, [])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    executeCompare(productA, productB)
  }

  const pA = result?.product_a
  const pB = result?.product_b

  return (
    <div className="space-y-10 pb-20">
      {/* ────────────────────────────────────────────────────────── */}
      {/* 1. SEARCH & CONTENDER INPUT BAR                            */}
      {/* ────────────────────────────────────────────────────────── */}
      <section className="rounded-3xl border border-border bg-card p-6 sm:p-8 shadow-sm space-y-6">
        <div>
          <Badge variant="outline" className="gap-1 border-primary/30 text-primary px-3 py-1 text-xs">
            <Globe className="size-3.5" /> Open Web Product Comparison
          </Badge>
          <h2 className="mt-3 text-2xl sm:text-3xl font-bold tracking-tight font-heading text-foreground">
            Head-to-Head Audio Gear Showdown
          </h2>
          <p className="mt-1.5 text-sm text-muted-foreground max-w-3xl">
            Type any two headphones or earbuds available in India. Our DuckDuckGo engine synthesizes live technical specifications, Indian market pricing, and customer review consensus to determine the winner.
          </p>
        </div>

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Product A Input */}
            <div className="space-y-2 rounded-2xl border border-border/70 bg-muted/20 p-4">
              <label htmlFor="input-prod-a" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center justify-between">
                <span>Product 1 (Contender A)</span>
                <span className="text-[10px] text-primary font-mono">Any Model / Brand</span>
              </label>
              <div className="relative">
                <Search className="absolute left-3.5 top-3 size-4 text-muted-foreground" />
                <Input
                  id="input-prod-a"
                  value={productA}
                  onChange={(e) => setProductA(e.target.value)}
                  placeholder="e.g. Sony WH-1000XM5"
                  className="pl-10 h-11 bg-background rounded-xl"
                />
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {QUICK_SUGGESTIONS.slice(0, 4).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setProductA(s)}
                    className="text-[11px] px-2 py-0.5 rounded-md border border-border/60 bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Product B Input */}
            <div className="space-y-2 rounded-2xl border border-border/70 bg-muted/20 p-4">
              <label htmlFor="input-prod-b" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center justify-between">
                <span>Product 2 (Contender B)</span>
                <span className="text-[10px] text-primary font-mono">Any Model / Brand</span>
              </label>
              <div className="relative">
                <Search className="absolute left-3.5 top-3 size-4 text-muted-foreground" />
                <Input
                  id="input-prod-b"
                  value={productB}
                  onChange={(e) => setProductB(e.target.value)}
                  placeholder="e.g. Bose QuietComfort 45"
                  className="pl-10 h-11 bg-background rounded-xl"
                />
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {QUICK_SUGGESTIONS.slice(4, 8).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setProductB(s)}
                    className="text-[11px] px-2 py-0.5 rounded-md border border-border/60 bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
            <Button
              type="submit"
              disabled={loading}
              size="lg"
              className="h-12 px-8 rounded-xl font-semibold gap-2 shadow-sm"
            >
              {loading ? (
                <>Analyzing Live Web Specs...</>
              ) : (
                <>
                  <Scale className="size-4" /> Compare Live Web Data
                </>
              )}
            </Button>

            <span className="text-xs text-muted-foreground">
              Powered by DuckDuckGo Search (Zero API keys • 100% Free)
            </span>
          </div>
        </form>

        {/* Quick Matchup Presets */}
        <div className="border-t border-border/60 pt-4 space-y-3">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="size-3.5 text-primary" /> Popular Matchups
          </span>
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            {POPULAR_MATCHUPS.map((m) => (
              <button
                key={m.title}
                type="button"
                onClick={() => {
                  setProductA(m.prodA)
                  setProductB(m.prodB)
                  executeCompare(m.prodA, m.prodB)
                }}
                className="flex flex-col items-start rounded-xl border border-border/70 bg-background/60 p-3 text-left hover:border-primary/50 hover:bg-muted/40 transition-all text-xs"
              >
                <span className="font-bold text-foreground line-clamp-1">{m.title}</span>
                <span className="mt-1 text-[11px] text-muted-foreground line-clamp-1">{m.desc}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ────────────────────────────────────────────────────────── */}
      {/* 2. LOADING SKELETON                                        */}
      {/* ────────────────────────────────────────────────────────── */}
      {loading && (
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Skeleton className="h-64 w-full rounded-3xl" />
            <Skeleton className="h-64 w-full rounded-3xl" />
          </div>
          <Skeleton className="h-80 w-full rounded-3xl" />
        </div>
      )}

      {/* ────────────────────────────────────────────────────────── */}
      {/* 3. COMPARISON RESULTS                                      */}
      {/* ────────────────────────────────────────────────────────── */}
      {!loading && result && pA && pB && (
        <div className="space-y-8 animate-in fade-in duration-300">
          {/* Verdict Banner */}
          <div className="rounded-3xl border border-primary/30 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent p-6 sm:p-8 flex items-start gap-4">
            <div className="rounded-2xl bg-primary/20 p-3 text-primary shrink-0">
              <Trophy className="size-6" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge className="bg-primary text-primary-foreground text-xs font-semibold">
                  Executive Verdict
                </Badge>
                <span className="text-xs text-muted-foreground">Synthesized from customer reviews &amp; acoustic benchmarks</span>
              </div>
              <h3 className="text-lg sm:text-xl font-bold text-foreground pt-1">
                {result.verdict}
              </h3>
            </div>
          </div>

          {/* Side-by-Side Contender Cards */}
          <div className="grid gap-6 md:grid-cols-2">
            {/* Contender A */}
            <div className="flex flex-col justify-between rounded-3xl border border-border bg-card p-6 sm:p-7 shadow-xs">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="text-xs capitalize font-medium">
                    {pA.category === "headphones" ? "🎧 Over-Ear Headphones" : "🎧 TWS Earbuds"}
                  </Badge>
                  <span className="text-xs font-semibold text-muted-foreground uppercase">{pA.brand}</span>
                </div>

                <div>
                  <h3 className="text-xl sm:text-2xl font-bold font-heading text-foreground">
                    {pA.name}
                  </h3>
                  <div className="mt-2 flex items-center gap-2 text-xs">
                    <span className="inline-flex items-center gap-1 font-bold text-amber-500">
                      <Star className="size-3.5 fill-amber-500" />
                      {pA.rating}
                    </span>
                    <span className="text-muted-foreground">({pA.reviews_count} reviews)</span>
                  </div>
                </div>

                <div className="rounded-2xl bg-muted/40 p-4 border border-border/50">
                  <span className="text-xs text-muted-foreground font-medium">Verified Indian Price</span>
                  <div className="mt-0.5 text-2xl font-black font-mono text-foreground">
                    {pA.price_str}
                  </div>
                </div>

                {/* Pros */}
                <div className="space-y-1.5 pt-2">
                  <span className="text-xs font-semibold text-foreground uppercase tracking-wider">Top Advantages:</span>
                  {pA.pros.map((pro) => (
                    <p key={pro} className="text-xs text-emerald-600 dark:text-emerald-400 flex items-start gap-1.5">
                      <CheckCircle2 className="size-3.5 shrink-0 mt-0.5" />
                      <span>{pro}</span>
                    </p>
                  ))}
                </div>

                {/* Cons */}
                <div className="space-y-1.5 pt-1">
                  <span className="text-xs font-semibold text-foreground uppercase tracking-wider">Known Trade-Offs:</span>
                  {pA.cons.map((con) => (
                    <p key={con} className="text-xs text-rose-600 dark:text-rose-400 flex items-start gap-1.5">
                      <XCircle className="size-3.5 shrink-0 mt-0.5" />
                      <span>{con}</span>
                    </p>
                  ))}
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-border">
                <a
                  href={pA.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-primary text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  View on {pA.merchant} <ExternalLink className="size-3.5" />
                </a>
              </div>
            </div>

            {/* Contender B */}
            <div className="flex flex-col justify-between rounded-3xl border border-border bg-card p-6 sm:p-7 shadow-xs">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="text-xs capitalize font-medium">
                    {pB.category === "headphones" ? "🎧 Over-Ear Headphones" : "🎧 TWS Earbuds"}
                  </Badge>
                  <span className="text-xs font-semibold text-muted-foreground uppercase">{pB.brand}</span>
                </div>

                <div>
                  <h3 className="text-xl sm:text-2xl font-bold font-heading text-foreground">
                    {pB.name}
                  </h3>
                  <div className="mt-2 flex items-center gap-2 text-xs">
                    <span className="inline-flex items-center gap-1 font-bold text-amber-500">
                      <Star className="size-3.5 fill-amber-500" />
                      {pB.rating}
                    </span>
                    <span className="text-muted-foreground">({pB.reviews_count} reviews)</span>
                  </div>
                </div>

                <div className="rounded-2xl bg-muted/40 p-4 border border-border/50">
                  <span className="text-xs text-muted-foreground font-medium">Verified Indian Price</span>
                  <div className="mt-0.5 text-2xl font-black font-mono text-foreground">
                    {pB.price_str}
                  </div>
                </div>

                {/* Pros */}
                <div className="space-y-1.5 pt-2">
                  <span className="text-xs font-semibold text-foreground uppercase tracking-wider">Top Advantages:</span>
                  {pB.pros.map((pro) => (
                    <p key={pro} className="text-xs text-emerald-600 dark:text-emerald-400 flex items-start gap-1.5">
                      <CheckCircle2 className="size-3.5 shrink-0 mt-0.5" />
                      <span>{pro}</span>
                    </p>
                  ))}
                </div>

                {/* Cons */}
                <div className="space-y-1.5 pt-1">
                  <span className="text-xs font-semibold text-foreground uppercase tracking-wider">Known Trade-Offs:</span>
                  {pB.cons.map((con) => (
                    <p key={con} className="text-xs text-rose-600 dark:text-rose-400 flex items-start gap-1.5">
                      <XCircle className="size-3.5 shrink-0 mt-0.5" />
                      <span>{con}</span>
                    </p>
                  ))}
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-border">
                <a
                  href={pB.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-primary text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  View on {pB.merchant} <ExternalLink className="size-3.5" />
                </a>
              </div>
            </div>
          </div>

          {/* ────────────────────────────────────────────────────────── */}
          {/* 4. HEAD-TO-HEAD ASPECT WINNERS MATRIX                      */}
          {/* ────────────────────────────────────────────────────────── */}
          <div className="rounded-3xl border border-border bg-card p-6 sm:p-8 space-y-6">
            <div>
              <h3 className="text-xl font-bold font-heading text-foreground flex items-center gap-2">
                <Award className="size-5 text-primary" />
                Head-to-Head Aspect Winners
              </h3>
              <p className="text-xs text-muted-foreground mt-1">
                Comparative breakdown across 7 primary audio dimensions (Scale of 1–10).
              </p>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-border/70">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-muted-foreground uppercase text-[11px] font-semibold">
                    <th className="py-3.5 px-4 w-[160px]">Aspect</th>
                    <th className="py-3.5 px-4">{pA.name}</th>
                    <th className="py-3.5 px-4">{pB.name}</th>
                    <th className="py-3.5 px-4 w-[220px]">Winner</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {[
                    { key: "sound", label: "Sound Quality", icon: "🎵" },
                    { key: "bass", label: "Bass & Low-End", icon: "🔊" },
                    { key: "battery", label: "Battery Playtime", icon: "🔋" },
                    { key: "comfort", label: "Comfort & Long Wear", icon: "☁️" },
                    { key: "mic", label: "Microphone & Calls", icon: "🎙️" },
                    { key: "anc", label: "Active Noise Cancellation", icon: "🛡️" },
                    { key: "value", label: "Value for Money", icon: "💰" },
                  ].map((row) => {
                    const sA = pA.scores[row.key] ?? 7.5
                    const sB = pB.scores[row.key] ?? 7.5
                    const winner = result.winners[row.key]
                    const isWinnerA = winner === pA.name
                    const isWinnerB = winner === pB.name

                    return (
                      <tr key={row.key} className="hover:bg-muted/30 transition-colors">
                        <td className="py-3.5 px-4 font-semibold text-foreground">
                          <span className="mr-1.5">{row.icon}</span>
                          {row.label}
                        </td>
                        <td className="py-3.5 px-4 font-mono">
                          <span className={cn(isWinnerA ? "font-bold text-primary" : "text-muted-foreground")}>
                            {sA.toFixed(1)} / 10
                          </span>
                        </td>
                        <td className="py-3.5 px-4 font-mono">
                          <span className={cn(isWinnerB ? "font-bold text-primary" : "text-muted-foreground")}>
                            {sB.toFixed(1)} / 10
                          </span>
                        </td>
                        <td className="py-3.5 px-4 font-semibold">
                          <span
                            className={cn(
                              "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold border",
                              isWinnerA && "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30",
                              isWinnerB && "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/30",
                              !isWinnerA && !isWinnerB && "bg-muted text-muted-foreground border-border"
                            )}
                          >
                            {isWinnerA ? `🏆 ${pA.name.slice(0, 22)}` : isWinnerB ? `🏆 ${pB.name.slice(0, 22)}` : "🤝 Comparable"}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* ────────────────────────────────────────────────────────── */}
          {/* 5. DETAILED TECHNICAL SPECIFICATIONS MATRIX                */}
          {/* ────────────────────────────────────────────────────────── */}
          <div className="rounded-3xl border border-border bg-card p-6 sm:p-8 space-y-6">
            <div>
              <h3 className="text-xl font-bold font-heading text-foreground flex items-center gap-2">
                <Zap className="size-5 text-primary" />
                Technical Specifications Comparison
              </h3>
              <p className="text-xs text-muted-foreground mt-1">
                Hardware specifications and connectivity parameters.
              </p>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-border/70">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-muted-foreground uppercase text-[11px] font-semibold">
                    <th className="py-3.5 px-4 w-[180px]">Specification</th>
                    <th className="py-3.5 px-4 font-bold text-foreground">{pA.name}</th>
                    <th className="py-3.5 px-4 font-bold text-foreground">{pB.name}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  <tr>
                    <td className="py-3.5 px-4 font-semibold text-muted-foreground">Form Factor</td>
                    <td className="py-3.5 px-4 capitalize font-medium">{pA.category}</td>
                    <td className="py-3.5 px-4 capitalize font-medium">{pB.category}</td>
                  </tr>
                  <tr>
                    <td className="py-3.5 px-4 font-semibold text-muted-foreground">Driver Architecture</td>
                    <td className="py-3.5 px-4 font-medium">{pA.specs.driver}</td>
                    <td className="py-3.5 px-4 font-medium">{pB.specs.driver}</td>
                  </tr>
                  <tr>
                    <td className="py-3.5 px-4 font-semibold text-muted-foreground">Battery Playtime</td>
                    <td className="py-3.5 px-4 font-medium">{pA.specs.battery}</td>
                    <td className="py-3.5 px-4 font-medium">{pB.specs.battery}</td>
                  </tr>
                  <tr>
                    <td className="py-3.5 px-4 font-semibold text-muted-foreground">Noise Cancellation</td>
                    <td className="py-3.5 px-4 font-medium">{pA.specs.anc}</td>
                    <td className="py-3.5 px-4 font-medium">{pB.specs.anc}</td>
                  </tr>
                  <tr>
                    <td className="py-3.5 px-4 font-semibold text-muted-foreground">Bluetooth &amp; Codecs</td>
                    <td className="py-3.5 px-4 font-medium">{pA.specs.bluetooth} • {pA.specs.codecs}</td>
                    <td className="py-3.5 px-4 font-medium">{pB.specs.bluetooth} • {pB.specs.codecs}</td>
                  </tr>
                  <tr>
                    <td className="py-3.5 px-4 font-semibold text-muted-foreground">Weight</td>
                    <td className="py-3.5 px-4 font-medium">{pA.specs.weight}</td>
                    <td className="py-3.5 px-4 font-medium">{pB.specs.weight}</td>
                  </tr>
                  <tr>
                    <td className="py-3.5 px-4 font-semibold text-muted-foreground">Retail Price</td>
                    <td className="py-3.5 px-4 font-bold font-mono text-foreground">{pA.price_str}</td>
                    <td className="py-3.5 px-4 font-bold font-mono text-foreground">{pB.price_str}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
