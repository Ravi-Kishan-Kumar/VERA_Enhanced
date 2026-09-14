import type { Metadata } from "next";
import Link from "next/link";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "./globals.css";
import { Navigation } from "@/components/Navigation";

export const metadata: Metadata = { title: { default: "VERA — Beyond the star rating", template: "%s | VERA" }, description: "Analyze earbud review experiences, explore aspect sentiment, and compare products with uncertainty-aware scores." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><a className="skip-link" href="#main">Skip to content</a><Navigation/><main id="main" className="page-shell">{children}</main><footer className="site-footer"><span>VERA <span className="footer-dot">/</span> Verified Experience & Review Analyzer</span><Link href="/about">Scores are estimates. Understand the method <span aria-hidden="true">↗</span></Link></footer></body></html>;
}
