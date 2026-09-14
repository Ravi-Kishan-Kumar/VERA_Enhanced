import type { Metadata } from "next";
import Link from "next/link";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import { Navigation } from "@/components/Navigation";
import { ServiceStatus } from "@/components/ServiceStatus";
import { pageMetadata, siteUrl } from "@/lib/metadata";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { ...pageMetadata("VERA — Beyond the star rating", "Analyze earbud review experiences, explore aspect sentiment, and compare products with uncertainty-aware scores."), metadataBase: siteUrl, title: { default: "VERA — Beyond the star rating", template: "%s | VERA" } };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={cn(GeistSans.variable, GeistMono.variable)}><body><a className="skip-link" href="#main">Skip to content</a><Navigation/><main id="main" tabIndex={-1} className="page-shell"><ServiceStatus/>{children}</main><footer className="site-footer"><span>VERA <span className="footer-dot">/</span> Verified Experience & Review Analyzer</span><Link href="/about">Scores are estimates. Understand the method <span aria-hidden="true">↗</span></Link></footer></body></html>;
}
