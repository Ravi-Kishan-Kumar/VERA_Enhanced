import type { Metadata } from "next";
import Link from "next/link";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import { DotPattern } from "@/components/ui/dot-pattern"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ServiceStatus } from "@/components/vera/service-status"
import { Navigation } from "@/components/vera/navigation"
import { ThemeProvider } from "@/components/vera/theme-provider"
import { pageMetadata, siteUrl } from "@/lib/metadata";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { ...pageMetadata("VERA — Beyond the star rating", "Analyze earbud review experiences, explore aspect sentiment, and compare products with uncertainty-aware scores."), metadataBase: siteUrl, title: { default: "VERA — Beyond the star rating", template: "%s | VERA" } };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning className={cn(GeistSans.variable, GeistMono.variable)}><body className="min-h-dvh overflow-x-hidden bg-background font-sans text-foreground antialiased"><ThemeProvider><TooltipProvider delayDuration={250}><a className="fixed left-4 top-[-4rem] z-[60] rounded-control bg-primary px-4 py-2 text-sm font-medium text-primary-foreground focus:top-4" href="#main">Skip to content</a><div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden="true"><div className="absolute -left-32 -top-44 size-[32rem] rounded-full bg-primary/[0.055] blur-3xl"/><div className="absolute -right-32 top-48 size-[28rem] rounded-full bg-slate-400/[0.035] blur-3xl dark:bg-slate-400/[0.025]"/><DotPattern className="text-slate-500/[0.045] [mask-image:linear-gradient(to_bottom,black,transparent_72%)] dark:text-white/[0.035]"/></div><Navigation/><main id="main" tabIndex={-1} className="mx-auto min-h-[calc(100dvh-10rem)] w-full max-w-6xl px-4 pb-20 pt-10 outline-none sm:px-6 sm:pt-16"><ServiceStatus/>{children}</main><footer className="mx-auto flex w-full max-w-6xl flex-col gap-2 border-t border-border/80 px-4 py-8 text-[13px] text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6"><span>VERA — Verified Experience &amp; Review Analyzer</span><Link href="/about" className="min-h-11 content-center rounded-md underline-offset-4 hover:text-foreground hover:underline">Scores are estimates. Read the methodology</Link></footer><Toaster richColors closeButton/></TooltipProvider></ThemeProvider></body></html>;
}
