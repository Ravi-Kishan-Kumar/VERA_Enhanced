"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function Navigation() {
  const pathname = usePathname();
  return <header className="site-header"><div className="header-inner">
    <Link href="/" className="brand" aria-label="VERA home"><span className="brand-symbol" aria-hidden="true">V<span>·</span></span>VERA<span className="brand-caption">REVIEW INTELLIGENCE</span></Link>
    <nav aria-label="Main navigation">{[["/", "Analyzer"], ["/products", "Products"], ["/about", "Methodology"]].map(([href, label]) => <Link key={href} href={href} aria-current={(href === "/" ? pathname === "/" : pathname.startsWith(href)) ? "page" : undefined}>{label}</Link>)}</nav>
    <span className="domain-label"><span aria-hidden="true" className="tiny-square"/>EARBUDS / EN</span>
  </div></header>;
}
