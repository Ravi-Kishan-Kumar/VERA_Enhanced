"use client"

import { type ColumnDef, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table"
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, ChevronsUpDown, Minus, SlidersHorizontal } from "lucide-react"
import Link from "next/link"
import { useCallback, useEffect, useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { apiPage, errorMessage } from "@/lib/api"
import { ASPECTS, aspectName, score, type Product } from "@/lib/types"
import { cn } from "@/lib/utils"

type SortKey = "corrected_score" | "star_average" | "review_count" | "uncertainty"
type Order = "asc" | "desc"
type Density = "comfortable" | "compact"

const PAGE_SIZE = 25
const sortable: Record<SortKey, { label: string; defaultOrder: Order }> = {
  corrected_score: { label: "VERA score", defaultOrder: "desc" },
  star_average: { label: "Star average", defaultOrder: "desc" },
  uncertainty: { label: "Uncertainty", defaultOrder: "asc" },
  review_count: { label: "Reviews", defaultOrder: "desc" },
}

function RankChange({ current, previous }: { current: number | null; previous?: number | null }) {
  if (current == null || previous == null) return <span className="text-[10px] font-medium uppercase text-muted-foreground">New</span>
  const moved = previous - current
  if (moved === 0) return <Minus className="size-3.5 text-muted-foreground" aria-label="No rank change"/>
  return moved > 0 ? <span className="inline-flex items-center text-xs text-emerald-700 dark:text-emerald-300"><ArrowUp className="size-3"/>{moved}<span className="sr-only">positions</span></span> : <span className="inline-flex items-center text-xs text-red-700 dark:text-red-300"><ArrowDown className="size-3"/>{-moved}<span className="sr-only">positions</span></span>
}

function AspectChips({ product, limit = 2 }: { product: Product; limit?: number }) {
  const summary = product.aspect_summary
  if (!summary) return <span className="text-muted-foreground">—</span>
  const mentioned = ASPECTS.map((key) => ({ key, summary: summary[key] })).filter((row) => row.summary && row.summary.mention_count > 0)
  const strongest = [...mentioned].sort((left, right) => Math.abs(right.summary!.net_sentiment) - Math.abs(left.summary!.net_sentiment)).slice(0, limit)
  if (!strongest.length) return <span className="text-muted-foreground">—</span>
  return <div className="flex flex-wrap gap-1.5">{strongest.map(({ key, summary: aspect }) => <Badge key={key} variant="outline" className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", aspect!.net_sentiment > 0 ? "border-emerald-600/20 text-emerald-700 dark:text-emerald-300" : aspect!.net_sentiment < 0 ? "border-red-600/20 text-red-700 dark:text-red-300" : "text-muted-foreground")}>{aspect!.net_sentiment > 0 ? "+" : aspect!.net_sentiment < 0 ? "−" : ""}{aspectName(key)}</Badge>)}</div>
}

function ErrorPanel({ message, retry }: { message: string; retry: () => void }) {
  return <div role="alert" className="rounded-2xl border border-destructive/25 bg-card p-8 text-center"><h2 className="text-lg font-semibold">Rankings are temporarily unavailable</h2><p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">{message}</p><Button variant="outline" className="mt-5" onClick={retry}>Try again</Button></div>
}

export function ProductRankings() {
  const [sortBy, setSortBy] = useState<SortKey>("corrected_score")
  const [order, setOrder] = useState<Order>("desc")
  const [page, setPage] = useState(0)
  const [density, setDensity] = useState<Density>("comfortable")
  const [data, setData] = useState<{ items: Product[]; total: number } | null>(null)
  const [error, setError] = useState("")
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const query = new URLSearchParams({ sort_by: sortBy, order, limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) })
    apiPage<Product>(`/products?${query}`, { signal: controller.signal }).then((result) => { setData(result); setError("") }).catch((cause) => { if (!controller.signal.aborted) setError(errorMessage(cause)) })
    return () => controller.abort()
  }, [sortBy, order, page, reload])

  const sort = useCallback((key: SortKey) => {
    setData(null); setError(""); setPage(0)
    setOrder((current) => key === sortBy ? current === "desc" ? "asc" : "desc" : sortable[key].defaultOrder)
    setSortBy(key)
  }, [sortBy])

  const columns = useMemo<ColumnDef<Product>[]>(() => [
    { id: "rank", header: "Rank", cell: ({ row }) => <div className="flex items-center gap-2 font-mono"><strong>#{row.original.rank_position ?? "—"}</strong><RankChange current={row.original.rank_position} previous={row.original.previous_rank_position}/></div> },
    { id: "product", header: "Product", cell: ({ row }) => <Link href={`/products/${encodeURIComponent(row.original.asin)}`} className="grid max-w-80 gap-0.5 rounded-md font-medium hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><span className="truncate">{row.original.title || "Untitled product"}</span><span className="font-mono text-[11px] font-normal text-muted-foreground">{row.original.asin}</span></Link> },
    { id: "corrected_score", header: () => <SortButton column="corrected_score" sortBy={sortBy} order={order} onSort={sort}/>, cell: ({ row }) => <div><strong className="font-mono text-base tabular-nums text-primary">{score(row.original.corrected_score)}</strong><span className="ml-1.5 font-mono text-xs text-muted-foreground">from {score(row.original.star_average)}</span></div> },
    { id: "uncertainty", header: () => <SortButton column="uncertainty" sortBy={sortBy} order={order} onSort={sort}/>, cell: ({ row }) => <span className="font-mono tabular-nums">±{score(row.original.uncertainty)}</span> },
    { id: "review_count", header: () => <SortButton column="review_count" sortBy={sortBy} order={order} onSort={sort}/>, cell: ({ row }) => <span className="font-mono tabular-nums">{row.original.review_count.toLocaleString()}</span> },
    { id: "aspects", header: "Strongest signals", cell: ({ row }) => <AspectChips product={row.original}/> },
  ], [order, sort, sortBy])
  // TanStack Table intentionally returns callable table methods; React Compiler skips this hook.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({ data: data?.items ?? [], columns, getCoreRowModel: getCoreRowModel(), manualSorting: true })

  if (error) return <ErrorPanel message={error} retry={() => { setError(""); setData(null); setReload((value) => value + 1) }}/>
  if (!data) return <div aria-label="Loading rankings" role="status" className="grid gap-3">{Array.from({ length: 6 }, (_, index) => <Skeleton key={index} className="h-16 w-full rounded-xl"/>)}</div>
  if (data.total === 0) return <div className="rounded-2xl border border-dashed border-border bg-card/55 p-10 text-center"><h2 className="text-xl font-semibold">No ranked products yet</h2><p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">Products appear after a completed review includes a product ASIN.</p><Button asChild className="mt-5"><Link href="/">Analyze a review</Link></Button></div>

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
  return (
    <section aria-labelledby="rankings-table-title">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h2 id="rankings-table-title" className="text-sm font-medium">Current ranking</h2><p className="mt-1 font-mono text-xs text-muted-foreground">{data.total.toLocaleString()} products · page {page + 1} of {pages}</p></div><div className="flex items-center gap-2"><SlidersHorizontal className="size-4 text-muted-foreground" strokeWidth={1.5}/><ToggleGroup type="single" value={density} onValueChange={(value) => { if (value) setDensity(value as Density) }} aria-label="Table density"><ToggleGroupItem value="comfortable" className="min-h-9 px-3 text-xs">Comfortable</ToggleGroupItem><ToggleGroupItem value="compact" className="min-h-9 px-3 text-xs">Compact</ToggleGroupItem></ToggleGroup></div></div>
      <div className="hidden overflow-hidden rounded-2xl border border-border bg-card md:block"><Table><caption className="sr-only">Earbud products ranked by VERA corrected experience score</caption><TableHeader><TableRow>{table.getHeaderGroups()[0].headers.map((header) => <TableHead key={header.id} className="whitespace-nowrap">{header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}</TableHead>)}</TableRow></TableHeader><TableBody>{table.getRowModel().rows.map((row) => <TableRow key={row.id} className={cn("hover:bg-muted/45", density === "compact" && "h-12")}>{row.getVisibleCells().map((cell) => <TableCell key={cell.id} className={cn("py-4", density === "compact" && "py-2")}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>)}</TableRow>)}</TableBody></Table></div>
      <div className="grid gap-3 md:hidden">{data.items.map((product) => <Link key={product.asin} href={`/products/${encodeURIComponent(product.asin)}`} className="rounded-2xl border border-border bg-card p-4 transition-colors duration-150 hover:border-primary/30"><div className="flex items-start justify-between gap-4"><div><p className="line-clamp-2 font-medium">{product.title || "Untitled product"}</p><p className="mt-1 font-mono text-[11px] text-muted-foreground">{product.asin}</p></div><div className="text-right"><p className="font-mono text-xl font-semibold text-primary">{score(product.corrected_score)}</p><p className="text-[10px] text-muted-foreground">VERA score</p></div></div><div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-xs text-muted-foreground"><span className="flex items-center gap-2"><strong className="font-mono text-foreground">#{product.rank_position ?? "—"}</strong><RankChange current={product.rank_position} previous={product.previous_rank_position}/></span><span className="font-mono">±{score(product.uncertainty)} · {product.review_count} reviews</span></div><div className="mt-3"><AspectChips product={product} limit={3}/></div></Link>)}</div>
      <nav className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5" aria-label="Rankings pagination"><span className="font-mono text-xs text-muted-foreground">Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, data.total)} of {data.total}</span><div className="flex gap-2"><Button variant="outline" disabled={page === 0} onClick={() => { setData(null); setPage((value) => value - 1) }}><ArrowLeft/>Previous</Button><Button variant="outline" disabled={page + 1 >= pages} onClick={() => { setData(null); setPage((value) => value + 1) }}>Next<ArrowRight/></Button></div></nav>
    </section>
  )
}

function SortButton({ column, sortBy, order, onSort }: { column: SortKey; sortBy: SortKey; order: Order; onSort: (key: SortKey) => void }) {
  const active = sortBy === column
  return <Tooltip><TooltipTrigger asChild><button type="button" onClick={() => onSort(column)} className="inline-flex min-h-10 items-center gap-1 rounded-md font-medium hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label={`Sort by ${sortable[column].label}`} aria-pressed={active}>{sortable[column].label}{active ? order === "desc" ? <ArrowDown className="size-3.5"/> : <ArrowUp className="size-3.5"/> : <ChevronsUpDown className="size-3.5 text-muted-foreground"/>}</button></TooltipTrigger><TooltipContent>{active ? `${order === "desc" ? "Descending" : "Ascending"}; activate to reverse` : `Sort by ${sortable[column].label}`}</TooltipContent></Tooltip>
}
