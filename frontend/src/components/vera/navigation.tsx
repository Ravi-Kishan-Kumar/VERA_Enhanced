"use client"

import { BookOpen, Code2, Menu, Search } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { CommandPalette } from "@/components/vera/command-palette"
import { ThemeToggle } from "@/components/vera/theme-toggle"
import { cn } from "@/lib/utils"

const links = [
  { href: "/", label: "Analyze" },
  { href: "/products", label: "Rankings" },
  { href: "/advisor", label: "Advisor" },
  { href: "/insights", label: "Insights" },
  { href: "/chat", label: "Chatbot" },
  { href: "/about", label: "Methodology" },
]

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href)
}

export function Navigation() {
  const pathname = usePathname()
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
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[76rem] items-center gap-4 px-4 sm:px-6">
          <Link href="/" aria-label="VERA home" className="flex min-h-11 items-center gap-2 rounded-control pr-3 font-semibold tracking-[-0.02em] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2">
            <span className="size-2 rounded-[2px] bg-primary" aria-hidden="true" />
            VERA
          </Link>

          <nav aria-label="Main navigation" className="hidden items-center gap-1 md:flex">
            {links.map((link) => {
              const active = isActive(pathname, link.href)
              return (
                <Link key={link.href} href={link.href} aria-current={active ? "page" : undefined} className={cn("flex min-h-11 items-center rounded-control px-3 text-sm font-medium text-muted-foreground transition-colors duration-150 hover:bg-muted/70 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40", active && "bg-muted text-foreground")}>
                  {link.label}
                </Link>
              )
            })}
          </nav>

          <div className="ml-auto flex items-center gap-0.5">
            <Button variant="outline" className="hidden h-10 min-w-40 justify-between rounded-control bg-card px-3 text-muted-foreground lg:flex" onClick={() => setCommandOpen(true)}>
              <span className="flex items-center gap-2"><Search strokeWidth={1.5} />Search</span>
              <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[11px]">⌘K</kbd>
            </Button>
            <Tooltip><TooltipTrigger asChild><Button asChild variant="ghost" size="icon" className="hidden size-11 rounded-control sm:inline-flex"><a href="https://github.com/Surya-Narayan-M/Customer-rating-and-review-analysis" target="_blank" rel="noreferrer" aria-label="VERA source on GitHub"><Code2 strokeWidth={1.5}/></a></Button></TooltipTrigger><TooltipContent side="bottom">GitHub</TooltipContent></Tooltip>
            <Tooltip><TooltipTrigger asChild><Button asChild variant="ghost" size="icon" className="hidden size-11 rounded-control sm:inline-flex"><Link href="/about" aria-label="Read VERA methodology"><BookOpen strokeWidth={1.5}/></Link></Button></TooltipTrigger><TooltipContent side="bottom">Methodology</TooltipContent></Tooltip>
            <ThemeToggle />
            <Sheet>
              <SheetTrigger asChild><Button variant="ghost" size="icon" className="size-11 rounded-control md:hidden" aria-label="Open navigation"><Menu strokeWidth={1.5}/></Button></SheetTrigger>
              <SheetContent className="w-[min(88vw,22rem)] border-border bg-card p-3">
                <SheetHeader className="px-2 pt-4"><SheetTitle className="text-left text-lg font-semibold">VERA</SheetTitle><SheetDescription className="text-left">Review intelligence with visible uncertainty.</SheetDescription></SheetHeader>
                <nav aria-label="Mobile navigation" className="grid gap-1 py-5">
                  {links.map((link) => <SheetClose asChild key={link.href}><Link href={link.href} aria-current={isActive(pathname, link.href) ? "page" : undefined} className={cn("flex min-h-12 items-center rounded-control px-3 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground", isActive(pathname, link.href) && "bg-muted text-foreground")}>{link.label}</Link></SheetClose>)}
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
