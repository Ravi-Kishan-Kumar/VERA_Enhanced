"use client"

import { AlertTriangle, ArrowLeft, FileQuestion, LoaderCircle, RotateCcw } from "lucide-react"
import Link from "next/link"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="mx-auto my-20 max-w-xl rounded-2xl border border-destructive/25 bg-card p-8 text-center" role="alert"><AlertTriangle className="mx-auto size-6 text-destructive" strokeWidth={1.5}/><h1 className="mt-4 text-2xl font-semibold tracking-[-0.03em]">Unable to load this page</h1><p className="mt-3 text-sm leading-6 text-muted-foreground">{message}</p><div className="mt-6 flex justify-center gap-2">{retry && <Button onClick={retry}><RotateCcw/>Try again</Button>}<Button asChild variant="outline"><Link href="/"><ArrowLeft/>Analyzer</Link></Button></div></div>
}

export function EmptyState({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="mx-auto my-20 max-w-xl rounded-2xl border border-dashed border-border bg-card/60 p-8 text-center"><FileQuestion className="mx-auto size-6 text-primary" strokeWidth={1.5}/><h1 className="mt-4 text-2xl font-semibold tracking-[-0.03em]">{title}</h1><p className="mt-3 text-sm leading-6 text-muted-foreground">{children}</p><Button asChild className="mt-6"><Link href="/">Analyze a review</Link></Button></div>
}

export function LoadingState({ label = "Loading data" }: { label?: string }) {
  return <div className="grid gap-4 py-16" role="status" aria-label={label}><div className="flex items-center gap-2 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin motion-reduce:animate-none"/>{label}</div><Skeleton className="h-20 w-3/4"/><Skeleton className="h-56 w-full rounded-2xl"/></div>
}

