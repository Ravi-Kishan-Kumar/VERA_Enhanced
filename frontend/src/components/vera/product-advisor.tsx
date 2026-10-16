"use client"

import {
  ArrowRight,
  Award,
  Check,
  ChevronDown,
  ExternalLink,
  Filter,
  Globe,
  Headphones,
  Info,
  Layers,
  Percent,
  Search,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  Star,
  Tag,
  Zap,
} from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api } from "@/lib/api"
import type { AdvisorResponse, BracketSuggestions, ProductAdvisorItem, WebAdvisorResponse, WebProductItem } from "@/lib/types"
import { cn } from "@/lib/utils"

const INTEREST_CONFIGS = [
  { key: "sound_quality", label: "Sound & Audio Clarity", icon: Sparkles, desc: "Acoustic precision, highs & mids balance" },
  { key: "noise_cancellation", label: "Active Noise Cancellation (ANC)", icon: Zap, desc: "Blocking ambient commute & office noise" },
  { key: "bass", label: "Bass & Low-End Punch", icon: SlidersHorizontal, desc: "Deep sub-bass response and thump" },
  { key: "battery_life", label: "Battery Playtime", icon: Layers, desc: "Continuous playback hours and charging speed" },
  { key: "comfort", label: "Comfort & Long Wear", icon: Headphones, desc: "Low clamping pressure, ear cushion softness" },
  { key: "microphone", label: "Microphone & Calling", icon: Award, desc: "Clear speech isolation in windy/noisy conditions" },
  { key: "connectivity", label: "Bluetooth & Low Latency", icon: Zap, desc: "Stable pairing, multi-point, zero video lag" },
  { key: "value", label: "Value for Money", icon: Percent, desc: "Best performance per rupee spent" },
] as const

const QUICK_QUERIES = [
  "Gym workout earbuds with punchy bass and sweat resistance",
  "Comfortable over-ear headphones with clear mic for office calls",
  "Best active noise cancelling under ₹8,000 for frequent train travel",
  "Flagship audiophile sound with lossless wireless support",
]

export function ProductAdvisor() {
  const [brackets, setBrackets] = useState<BracketSuggestions | null>(null)
  const [recommendations, setRecommendations] = useState<ProductAdvisorItem[] | null>(null)
  const [webResults, setWebResults] = useState<WebAdvisorResponse | null>(null)
  const [searchMode, setSearchMode] = useState<"web" | "dataset">("web")
  const [totalMatches, setTotalMatches] = useState<number>(0)
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)

  // Filters
  const [category, setCategory] = useState<"all" | "earbuds" | "headphones">("all")
  const [priceBracket, setPriceBracket] = useState<"all" | "budget" | "mid" | "premium">("all")
  const [minPrice, setMinPrice] = useState<string>("")
  const [maxPrice, setMaxPrice] = useState<string>("")
  const [queryText, setQueryText] = useState<string>("")
  const [interests, setInterests] = useState<Record<string, number>>({
    sound_quality: 4,
    noise_cancellation: 4,
    bass: 3,
    battery_life: 3,
    comfort: 4,
    microphone: 3,
    connectivity: 3,
    value: 4,
  })

  // Selected bracket tab for browsing top 5
  const [browseCategory, setBrowseCategory] = useState<"earbuds" | "headphones">("earbuds")
  const [browseBracket, setBrowseBracket] = useState<"budget" | "mid" | "premium">("mid")

  useEffect(() => {
    let active = true
    api<BracketSuggestions>("/advisor/brackets")
      .then((data) => {
        if (!active) return
        setBrackets(data)
        setLoading(false)
      })
      .catch((err) => {
        if (!active) return
        toast.error("Failed to load product suggestions.")
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const handleInterestChange = (key: string, value: number) => {
    setInterests((prev) => ({ ...prev, [key]: value }))
  }

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    setSearching(true)
    try {
      const payload = {
        category,
        price_bracket: priceBracket,
        min_price: minPrice ? parseFloat(minPrice) : null,
        max_price: maxPrice ? parseFloat(maxPrice) : null,
        query_text: queryText.trim() || null,
        interests,
      }

      if (searchMode === "web") {
        const res = await api<WebAdvisorResponse>("/advisor/web-recommend", {
          method: "POST",
          body: JSON.stringify(payload),
        })
        setWebResults(res)
        setRecommendations(null)
      } else {
        const res = await api<AdvisorResponse>("/advisor/recommend", {
          method: "POST",
          body: JSON.stringify(payload),
        })
        setRecommendations(res.recommendations)
        setTotalMatches(res.total_matches)
        setWebResults(null)
      }
    } catch (err) {
      toast.error("Recommendation search failed.")
    } finally {
      setSearching(false)
    }
  }

  const handleClearFilters = () => {
    setCategory("all")
    setPriceBracket("all")
    setMinPrice("")
    setMaxPrice("")
    setQueryText("")
    setRecommendations(null)
    setWebResults(null)
    setInterests({
      sound_quality: 3,
      noise_cancellation: 3,
      bass: 3,
      battery_life: 3,
      comfort: 3,
      microphone: 3,
      connectivity: 3,
      value: 3,
    })
  }

  return (
    <div className="space-y-12 pb-16">
      {/* ────────────────────────────────────────────────────────── */}
      {/* 1. OVERALL TOP 3 IN INDIA HERO SHOWCASE                    */}
      {/* ────────────────────────────────────────────────────────── */}
      <section aria-labelledby="top-3-title" className="space-y-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Badge className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30 gap-1.5 py-1 px-3">
                <Award className="size-3.5" /> National Ranking
              </Badge>
              <span className="text-xs font-medium text-muted-foreground">Calibrated over 5,196+ reviews</span>
            </div>
            <h2 id="top-3-title" className="mt-2 text-2xl sm:text-3xl font-bold tracking-tight text-foreground font-heading">
              Overall Top 3 in India
            </h2>
            <p className="text-sm text-muted-foreground max-w-2xl mt-1">
              The highest-performing audio devices in India across all categories, evaluated for acoustics, build, real-world Indian conditions, and price-to-performance.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="grid gap-6 md:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-64 animate-pulse rounded-2xl border border-border/60 bg-muted/20 p-6" />
            ))}
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-3">
            {brackets?.overall_top_3_india.map((item, idx) => {
              const badgeColors = [
                "border-amber-500/50 bg-amber-500/10 text-amber-600 dark:text-amber-400",
                "border-blue-500/50 bg-blue-500/10 text-blue-600 dark:text-blue-400",
                "border-emerald-500/50 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
              ]
              return (
                <div
                  key={item.asin}
                  className="relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border/80 bg-card p-6 shadow-sm transition-all hover:border-primary/50 hover:shadow-md"
                >
                  <div className="absolute top-0 right-0 h-28 w-28 -mr-8 -mt-8 rounded-full bg-primary/5 blur-2xl" />
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold", badgeColors[idx % 3])}>
                        <Award className="size-3.5" />
                        {item.award || `#${idx + 1} Ranked in India`}
                      </span>
                      <span className="text-xs font-mono font-medium text-muted-foreground uppercase">
                        {item.category === "earbuds" ? "TWS Earbuds" : "Over-Ear"}
                      </span>
                    </div>

                    <h3 className="mt-4 text-lg font-bold tracking-tight text-foreground line-clamp-2">
                      {item.title}
                    </h3>
                    <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
                      {item.award_reason || "Exceptional acoustic fidelity and proven real-world reliability."}
                    </p>

                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {item.top_strengths.map((str) => (
                        <span key={str} className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-foreground/80">
                          ✓ {str}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="mt-6 border-t border-border/60 pt-4">
                    <div className="flex items-end justify-between">
                      <div>
                        <span className="text-[11px] font-medium text-muted-foreground">VERA Calibrated Score</span>
                        <div className="flex items-baseline gap-1.5 mt-0.5">
                          <span className="text-2xl font-extrabold text-foreground">{item.corrected_score.toFixed(2)}</span>
                          <span className="text-xs text-muted-foreground">/ 5.0</span>
                          <span className="text-[11px] text-muted-foreground">±{item.uncertainty.toFixed(2)}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-[11px] font-medium text-muted-foreground">Typical Price</span>
                        <div className="text-lg font-bold text-foreground">
                          {item.price_inr ? `₹${item.price_inr.toLocaleString("en-IN")}` : "Check Price"}
                        </div>
                      </div>
                    </div>

                    <Link
                      href={`/products/${encodeURIComponent(item.asin)}`}
                      className="mt-4 flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-primary/10 text-xs font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
                    >
                      Inspect Full Telemetry &amp; Reviews <ArrowRight className="size-3.5" />
                    </Link>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* ────────────────────────────────────────────────────────── */}
      {/* 2. RAG & MULTI-ASPECT SEARCH & FILTER ADVISOR             */}
      {/* ────────────────────────────────────────────────────────── */}
      <section aria-labelledby="advisor-query-title" className="rounded-3xl border border-border bg-card p-6 sm:p-8 shadow-sm">
        <div className="max-w-3xl">
          <Badge variant="outline" className="gap-1 border-primary/30 text-primary px-3 py-1 text-xs">
            <Sparkles className="size-3" /> Intelligent Recommendation Engine
          </Badge>
          <h2 id="advisor-query-title" className="mt-3 text-2xl sm:text-3xl font-bold tracking-tight font-heading">
            Find Your Ideal Earbuds or Headphones
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Filter by your personal points of interest (Audio, ANC, Connectivity, Price, Mic, Comfort) and describe what you want in plain words. Our RAG engine evaluates aspect sentiments and calibration bounds to suggest the top match.
          </p>

          {/* Mode Switcher */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mt-6 pt-4 border-t border-border">
            <div className="flex items-center gap-1.5 p-1 bg-muted/60 rounded-xl border border-border w-fit">
              <button
                type="button"
                onClick={() => { setSearchMode("web"); setRecommendations(null); }}
                className={cn(
                  "flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all",
                  searchMode === "web"
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Globe className="size-3.5" />
                🌐 Live Indian Market (Web)
              </button>
              <button
                type="button"
                onClick={() => { setSearchMode("dataset"); setWebResults(null); }}
                className={cn(
                  "flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all",
                  searchMode === "dataset"
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Tag className="size-3.5" />
                📦 VERA Trained Dataset
              </button>
            </div>

            <div className="text-xs text-muted-foreground">
              {searchMode === "web" ? (
                <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
                  <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
                  Live Indian E-Commerce (Amazon.in / Flipkart / Croma)
                </span>
              ) : (
                <span>Benchmarked across 5,196 calibrated reviews</span>
              )}
            </div>
          </div>
        </div>

        <form onSubmit={handleSearch} className="mt-8 space-y-8">
          {/* Natural language query input */}
          <div className="space-y-2">
            <Label htmlFor="search-description" className="text-sm font-semibold">
              Describe what you need <span className="text-xs font-normal text-muted-foreground">(Optional text query)</span>
            </Label>
            <div className="relative">
              <Search className="absolute left-3.5 top-3.5 size-4 text-muted-foreground" />
              <Input
                id="search-description"
                placeholder="e.g. Bass-heavy earbuds with long battery for gym workouts, or comfortable over-ear headphones for office calls..."
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                className="h-12 pl-10 pr-4 rounded-xl bg-background"
              />
            </div>
            {/* Quick Suggestions */}
            <div className="flex flex-wrap items-center gap-2 pt-1 text-xs text-muted-foreground">
              <span>Quick ideas:</span>
              {QUICK_QUERIES.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => setQueryText(q)}
                  className="rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs text-foreground/80 hover:bg-muted hover:text-foreground transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          {/* Primary Filters: Category & Price Bracket */}
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {/* Category Select */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Category</Label>
              <div className="flex gap-2">
                {[
                  { id: "all", label: "All Audio" },
                  { id: "earbuds", label: "🎧 Earbuds" },
                  { id: "headphones", label: "🎧 Headphones" },
                ].map((item) => (
                  <Button
                    key={item.id}
                    type="button"
                    size="sm"
                    variant={category === item.id ? "default" : "outline"}
                    className="flex-1 rounded-lg text-xs"
                    onClick={() => setCategory(item.id as any)}
                  >
                    {item.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Price Bracket */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Price Bracket (India)</Label>
              <div className="flex gap-1.5">
                {[
                  { id: "all", label: "All" },
                  { id: "budget", label: "< ₹2.5k" },
                  { id: "mid", label: "₹2.5k–₹8k" },
                  { id: "premium", label: "> ₹8k" },
                ].map((item) => (
                  <Button
                    key={item.id}
                    type="button"
                    size="sm"
                    variant={priceBracket === item.id ? "default" : "outline"}
                    className="flex-1 rounded-lg text-xs px-2"
                    onClick={() => setPriceBracket(item.id as any)}
                  >
                    {item.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Custom Min / Max Price in INR */}
            <div className="space-y-2 sm:col-span-2 lg:col-span-1">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Custom Budget (INR ₹)</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  placeholder="Min ₹"
                  value={minPrice}
                  onChange={(e) => setMinPrice(e.target.value)}
                  className="h-9 rounded-lg bg-background text-xs"
                />
                <span className="text-muted-foreground text-xs">to</span>
                <Input
                  type="number"
                  placeholder="Max ₹"
                  value={maxPrice}
                  onChange={(e) => setMaxPrice(e.target.value)}
                  className="h-9 rounded-lg bg-background text-xs"
                />
              </div>
            </div>
          </div>

          {/* Points of Interest: Priority Sliders / Ratings */}
          <div className="space-y-4 rounded-2xl border border-border/70 bg-muted/20 p-5">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-semibold text-foreground">Your Points of Interest &amp; Priorities</h4>
                <p className="text-xs text-muted-foreground">Rate how important each feature is to you (1 = Low, 5 = Critical)</p>
              </div>
              <Badge variant="outline" className="text-[11px]">8 Dimensions Evaluated</Badge>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 pt-2">
              {INTEREST_CONFIGS.map((item) => {
                const val = interests[item.key] || 3
                return (
                  <div key={item.key} className="rounded-xl border border-border/80 bg-card p-3 shadow-2xs space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-foreground">{item.label}</span>
                      <span className="font-mono text-xs font-bold text-primary">{val} / 5</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {[1, 2, 3, 4, 5].map((lvl) => (
                        <button
                          key={lvl}
                          type="button"
                          onClick={() => handleInterestChange(item.key, lvl)}
                          className={cn(
                            "h-6 flex-1 rounded text-[11px] font-semibold transition-all",
                            lvl <= val
                              ? "bg-primary text-primary-foreground shadow-2xs"
                              : "bg-muted text-muted-foreground hover:bg-muted/80"
                          )}
                        >
                          {lvl}
                        </button>
                      ))}
                    </div>
                    <p className="text-[10px] text-muted-foreground leading-tight">{item.desc}</p>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Search CTA */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
            <Button
              type="submit"
              disabled={searching}
              size="lg"
              className="h-12 px-8 rounded-xl font-semibold gap-2 shadow-sm"
            >
              {searching ? (
                <>Computing RAG Multi-Aspect Matches...</>
              ) : (
                <>
                  <Sparkles className="size-4" /> Compare &amp; Suggest Best Matches
                </>
              )}
            </Button>

            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleClearFilters}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Reset Filters
            </Button>
          </div>
        </form>

        {/* ────────────────────────────────────────────────────────── */}
        {/* LIVE WEB RECOMMENDATION RESULTS                            */}
        {/* ────────────────────────────────────────────────────────── */}
        {webResults && (
          <div className="mt-10 border-t border-border pt-8 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-xl font-bold font-heading text-foreground flex items-center gap-2">
                  <Globe className="size-5 text-emerald-500" />
                  Live Indian Market Suggestions
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {webResults.live_market_insights}
                </p>
              </div>
              <Badge className="w-fit bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-xs font-semibold">
                DuckDuckGo Live Search • {webResults.matches?.length ?? webResults.total_analyzed} Matching Models
              </Badge>
            </div>

            {/* Active Filter Pills */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-muted-foreground font-medium">Active filters:</span>
              <Badge variant="outline" className="capitalize text-[11px] font-medium">
                Category: {category === "headphones" ? "🎧 Headphones" : category === "earbuds" ? "🎧 Earbuds" : "All Audio"}
              </Badge>
              {(minPrice || maxPrice) ? (
                <Badge variant="outline" className="text-[11px] font-medium border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
                  Custom Budget: ₹{minPrice ? Number(minPrice).toLocaleString("en-IN") : "0"} – ₹{maxPrice ? Number(maxPrice).toLocaleString("en-IN") : "Any"}
                </Badge>
              ) : priceBracket !== "all" ? (
                <Badge variant="outline" className="capitalize text-[11px] font-medium">
                  Bracket: {priceBracket}
                </Badge>
              ) : null}
              {queryText && (
                <Badge variant="outline" className="text-[11px] font-medium">
                  Query: &quot;{queryText}&quot;
                </Badge>
              )}
            </div>

            {(!webResults.matches || webResults.matches.length === 0) ? (
              <div className="rounded-2xl border border-dashed border-border p-8 text-center space-y-2">
                <p className="font-semibold text-foreground">No audio products match this exact budget and category.</p>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  Try adjusting the Custom Budget min/max prices or select &quot;All Audio&quot; to see available options in India.
                </p>
                <Button variant="outline" size="sm" onClick={handleClearFilters} className="mt-3">
                  Reset Budget &amp; Filters
                </Button>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {webResults.matches.map((item) => (
                  <div
                    key={item.name}
                    className="flex flex-col justify-between rounded-2xl border border-border bg-background p-5 shadow-2xs hover:border-primary/50 transition-all hover:shadow-md"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        {item.match_score != null && (
                          <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-xs font-semibold">
                            {item.match_score}% Match
                          </Badge>
                        )}
                        <span className="text-[11px] font-mono text-muted-foreground uppercase px-2 py-0.5 rounded-full bg-muted">
                          {item.category === "headphones" ? "🎧 Headphone" : "🎧 Earbuds"} • {item.price_bracket}
                        </span>
                      </div>

                      <div className="mt-3 flex items-baseline justify-between gap-2">
                        <h4 className="text-base font-bold text-foreground line-clamp-1">
                          {item.name}
                        </h4>
                        <span className="text-xs font-semibold text-muted-foreground uppercase shrink-0">
                          {item.brand}
                        </span>
                      </div>

                      <div className="mt-1 flex items-center gap-2 text-xs">
                        <span className="inline-flex items-center gap-1 text-amber-500 font-bold">
                          <Star className="size-3.5 fill-amber-500" />
                          {item.rating}
                        </span>
                        <span className="text-muted-foreground">({item.reviews_count} reviews)</span>
                        <Badge variant="outline" className="text-[10px] py-0 px-1.5 ml-auto capitalize">
                          {item.category}
                        </Badge>
                      </div>

                      {/* Dynamic Match Reason */}
                      {item.match_reason && (
                        <div className="mt-2.5 rounded-lg bg-primary/5 border border-primary/20 px-2.5 py-1.5 text-[11px] text-primary font-medium">
                          🎯 {item.match_reason}
                        </div>
                      )}

                      {/* Specs */}
                      <div className="mt-3 rounded-xl bg-muted/30 p-2.5 text-[11px] space-y-1 border border-border/50">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Driver:</span>
                          <span className="font-medium text-foreground">{item.specs.driver}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Battery:</span>
                          <span className="font-medium text-foreground">{item.specs.battery}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">ANC / Call:</span>
                          <span className="font-medium text-foreground">{item.specs.anc}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Codecs:</span>
                          <span className="font-medium text-foreground">{item.specs.codecs}</span>
                        </div>
                      </div>

                      {/* Pros & Cons */}
                      <div className="mt-3 space-y-1">
                        {item.pros.slice(0, 2).map((p) => (
                          <p key={p} className="text-[11px] text-emerald-600 dark:text-emerald-400 line-clamp-1">
                            ✓ {p}
                          </p>
                        ))}
                      </div>
                    </div>

                    <div className="mt-5 border-t border-border/60 pt-3">
                      <div className="flex items-center justify-between text-xs mb-3">
                        <span className="text-muted-foreground">Market Price:</span>
                        <div className="text-base font-extrabold text-foreground font-mono">
                          {item.price_str}
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <Link
                          href={`/compare?product_a=${encodeURIComponent(item.name)}`}
                          className="flex h-9 items-center justify-center rounded-lg bg-muted text-xs font-semibold hover:bg-muted/80 text-foreground transition-colors"
                        >
                          Compare <ArrowRight className="size-3 ml-1" />
                        </Link>
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="flex h-9 items-center justify-center rounded-lg bg-primary text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors gap-1"
                        >
                          {item.merchant} <ExternalLink className="size-3" />
                        </a>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ────────────────────────────────────────────────────────── */}
        {/* RECOMMENDATION RESULTS IF SEARCHED                         */}
        {/* ────────────────────────────────────────────────────────── */}
        {recommendations && (
          <div className="mt-10 border-t border-border pt-8 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold font-heading text-foreground">
                  Personalized Recommendation Results
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Found {totalMatches} products ranked by aspect alignment and VERA calibrated reliability score.
                </p>
              </div>
              <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
                Top Matches Sorted
              </Badge>
            </div>

            {recommendations.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
                No products found matching those specific budget constraints. Try widening the price range.
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {recommendations.map((item, idx) => (
                  <div
                    key={item.asin}
                    className="flex flex-col justify-between rounded-xl border border-border bg-background p-5 shadow-2xs hover:border-primary/50 transition-all"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        {item.match_score != null && (
                          <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-xs font-semibold">
                            {item.match_score}% Match
                          </Badge>
                        )}
                        <span className="text-[11px] font-mono text-muted-foreground uppercase">
                          {item.bracket} bracket
                        </span>
                      </div>

                      <h4 className="mt-3 text-sm font-bold text-foreground line-clamp-2">
                        {item.title}
                      </h4>
                      <p className="mt-1 text-xs text-primary font-medium">
                        {item.reason}
                      </p>

                      <div className="mt-3 flex flex-wrap gap-1">
                        {item.top_strengths.map((str) => (
                          <span key={str} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                            ✓ {str}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="mt-5 border-t border-border/60 pt-3">
                      <div className="flex items-center justify-between text-xs">
                        <div>
                          <span className="text-muted-foreground">VERA Score: </span>
                          <span className="font-bold text-foreground">{item.corrected_score.toFixed(2)} / 5</span>
                        </div>
                        <div className="font-bold text-foreground">
                          {item.price_inr ? `₹${item.price_inr.toLocaleString("en-IN")}` : "—"}
                        </div>
                      </div>

                      <Link
                        href={`/products/${encodeURIComponent(item.asin)}`}
                        className="mt-3 flex h-8 items-center justify-center rounded-lg bg-muted text-xs font-medium hover:bg-primary hover:text-primary-foreground transition-colors"
                      >
                        Inspect Product <ArrowRight className="size-3 ml-1" />
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {/* ────────────────────────────────────────────────────────── */}
      {/* 3. TOP 5 FROM EACH BRACKET (BUDGET, MID, PREMIUM)         */}
      {/* ────────────────────────────────────────────────────────── */}
      <section aria-labelledby="brackets-title" className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="gap-1 border-primary/30 text-primary text-xs">
                <Tag className="size-3.5" /> Curated Tier Lists
              </Badge>
            </div>
            <h2 id="brackets-title" className="mt-2 text-2xl sm:text-3xl font-bold tracking-tight text-foreground font-heading">
              Top 5 in Each Price Bracket
            </h2>
            <p className="text-sm text-muted-foreground max-w-2xl mt-1">
              Side-by-side comparison of the top 5 models in Budget (&lt; ₹2,500), Mid-Range (₹2,500–₹8,000), and Premium (&gt; ₹8,000) for both Earbuds and Headphones.
            </p>
          </div>

          {/* Category Toggle */}
          <div className="flex rounded-xl border border-border bg-muted/40 p-1">
            <button
              type="button"
              onClick={() => setBrowseCategory("earbuds")}
              className={cn(
                "rounded-lg px-4 py-1.5 text-xs font-semibold transition-all",
                browseCategory === "earbuds"
                  ? "bg-card text-foreground shadow-2xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              🎧 Earbuds (TWS)
            </button>
            <button
              type="button"
              onClick={() => setBrowseCategory("headphones")}
              className={cn(
                "rounded-lg px-4 py-1.5 text-xs font-semibold transition-all",
                browseCategory === "headphones"
                  ? "bg-card text-foreground shadow-2xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              🎧 Over-Ear Headphones
            </button>
          </div>
        </div>

        {/* 3 Bracket Columns */}
        <div className="grid gap-6 lg:grid-cols-3">
          {(["budget", "mid", "premium"] as const).map((bracketKey) => {
            const bracketTitles = {
              budget: { name: "Budget Bracket", price: "< ₹2,500", desc: "Best value-for-money without serious defect traps" },
              mid: { name: "Mid-Range Bracket", price: "₹2,500 - ₹8,000", desc: "Sweet spot for Active Noise Cancelling & LDAC codecs" },
              premium: { name: "Premium Flagships", price: "> ₹8,000", desc: "Supreme acoustic engineering, spatial audio & luxury build" },
            }
            const info = bracketTitles[bracketKey]
            const list = brackets ? brackets[browseCategory][bracketKey] : []

            return (
              <div
                key={bracketKey}
                className="flex flex-col rounded-2xl border border-border bg-card p-5 shadow-2xs"
              >
                <div className="border-b border-border/70 pb-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold text-foreground text-base">{info.name}</h3>
                    <Badge variant="secondary" className="font-mono text-xs font-bold">
                      {info.price}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{info.desc}</p>
                </div>

                <div className="mt-4 flex-1 space-y-3">
                  {loading ? (
                    <div className="space-y-3">
                      {[1, 2, 3, 4, 5].map((i) => (
                        <div key={i} className="h-20 animate-pulse rounded-xl bg-muted/30" />
                      ))}
                    </div>
                  ) : (
                    list.map((item, rank) => (
                      <Link
                        key={item.asin}
                        href={`/products/${encodeURIComponent(item.asin)}`}
                        className="group flex items-start gap-3 rounded-xl border border-border/60 bg-background/50 p-3.5 transition-all hover:border-primary/50 hover:bg-background hover:shadow-xs"
                      >
                        <span className={cn(
                          "flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-bold",
                          rank === 0
                            ? "bg-amber-500 text-amber-950 font-extrabold"
                            : rank === 1
                            ? "bg-slate-300 text-slate-800 dark:bg-slate-700 dark:text-slate-200"
                            : rank === 2
                            ? "bg-amber-700/60 text-amber-100"
                            : "bg-muted text-muted-foreground"
                        )}>
                          {rank + 1}
                        </span>

                        <div className="min-w-0 flex-1">
                          <h4 className="text-xs font-semibold text-foreground group-hover:text-primary transition-colors line-clamp-2">
                            {item.title}
                          </h4>
                          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                            <span className="font-bold text-foreground">
                              {item.price_inr ? `₹${item.price_inr.toLocaleString("en-IN")}` : "—"}
                            </span>
                            <span>•</span>
                            <span className="font-medium text-primary">
                              VERA {item.corrected_score.toFixed(2)} ★
                            </span>
                          </div>
                        </div>
                      </Link>
                    ))
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </section>
    </div>
  )
}
