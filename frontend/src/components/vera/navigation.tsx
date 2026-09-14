"use client"

import { BookOpen, Code2, Menu, Search } from "lucide-react"
import { motion, useReducedMotion } from "motion/react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { CommandPalette } from "@/components/vera/command-palette"
import { ThemeToggle } from "@/components/vera/theme-toggle"
import { EASE_OUT, motionDuration } from "@/lib/motion"
import { cn } from "@/lib/utils"

const links = [
  { href: "/", label: "Analyze" },
  { href: "/products", label: "Rankings" },
  { href: "/about", label: "Methodology" },
]

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href)
}

export function Navigation() {
  const pathname = usePathname()
  const reduced = useReducedMotion()
  const [commandOpen, setCommandOpen] = useState(false)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setCommandOpen((current) => !current)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  return (
    <>
      <header className="sticky top-3 z-40 mx-auto w-[calc(100%-2rem)] max-w-6xl rounded-2xl border border-white/60 bg-white/65 shadow-[0_1px_0_0_rgba(255,255,255,0.7)_inset,0_12px_32px_-16px_rgba(15,23,42,0.18)] ring-1 ring-slate-900/5 backdrop-blur-xl backdrop-saturate-150 supports-[not_(backdrop-filter:blur(1px))]:bg-white/95 dark:border-white/10 dark:bg-slate-900/55 dark:ring-white/5 dark:supports-[not_(backdrop-filter:blur(1px))]:bg-slate-900/95">
        <div className="flex h-14 items-center gap-2 px-2 sm:px-3">
          <Link href="/" aria-label="VERA home" className="flex min-h-11 items-center gap-2 rounded-[10px] px-2 font-semibold tracking-[-0.02em] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2">
            <span className="size-2 rounded-[2px] bg-primary" aria-hidden="true" />
            VERA
          </Link>

          <nav aria-label="Main navigation" className="ml-2 hidden items-center rounded-xl bg-slate-100/80 p-1 md:flex dark:bg-slate-800/70">
            {links.map((link) => {
              const active = isActive(pathname, link.href)
              return (
                <Link key={link.href} href={link.href} aria-current={active ? "page" : undefined} className={cn("relative flex min-h-9 items-center rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors duration-[120ms] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40", active && "text-foreground")}> 
                  {active && <motion.span layoutId="active-navigation" className="absolute inset-0 rounded-lg bg-background shadow-sm" transition={reduced ? { duration: 0 } : { duration: motionDuration.ui, ease: EASE_OUT }} />}
                  <span className="relative">{link.label}</span>
                </Link>
              )
            })}
          </nav>

          <div className="ml-auto flex items-center gap-0.5">
            <Button variant="ghost" className="hidden h-10 min-w-44 justify-between rounded-[10px] border border-border/80 bg-background/70 px-3 text-muted-foreground lg:flex" onClick={() => setCommandOpen(true)}>
              <span className="flex items-center gap-2"><Search strokeWidth={1.5} />Search</span>
              <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[11px]">⌘K</kbd>
            </Button>
            <Tooltip><TooltipTrigger asChild><Button asChild variant="ghost" size="icon" className="hidden size-11 rounded-[10px] sm:inline-flex"><a href="https://github.com/Surya-Narayan-M/Customer-rating-and-review-analysis" target="_blank" rel="noreferrer" aria-label="VERA source on GitHub"><Code2 strokeWidth={1.5}/></a></Button></TooltipTrigger><TooltipContent side="bottom">GitHub</TooltipContent></Tooltip>
            <Tooltip><TooltipTrigger asChild><Button asChild variant="ghost" size="icon" className="hidden size-11 rounded-[10px] sm:inline-flex"><Link href="/about" aria-label="Read VERA methodology"><BookOpen strokeWidth={1.5}/></Link></Button></TooltipTrigger><TooltipContent side="bottom">Methodology</TooltipContent></Tooltip>
            <ThemeToggle />
            <Sheet>
              <SheetTrigger asChild><Button variant="ghost" size="icon" className="size-11 rounded-[10px] md:hidden" aria-label="Open navigation"><Menu strokeWidth={1.5}/></Button></SheetTrigger>
              <SheetContent className="w-[min(88vw,22rem)] border-white/60 bg-white/90 p-3 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/90">
                <SheetHeader className="px-2 pt-4"><SheetTitle className="text-left text-lg font-semibold">VERA</SheetTitle><SheetDescription className="text-left">Review intelligence with visible uncertainty.</SheetDescription></SheetHeader>
                <nav aria-label="Mobile navigation" className="grid gap-1 py-5">
                  {links.map((link) => <SheetClose asChild key={link.href}><Link href={link.href} aria-current={isActive(pathname, link.href) ? "page" : undefined} className={cn("flex min-h-12 items-center rounded-[10px] px-3 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground", isActive(pathname, link.href) && "bg-muted text-foreground")}>{link.label}</Link></SheetClose>)}
                </nav>
                <Button variant="outline" className="h-11 justify-start" onClick={() => setCommandOpen(true)}><Search strokeWidth={1.5}/>Search products and pages</Button>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </header>
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen}/>
    </>
  )
}
