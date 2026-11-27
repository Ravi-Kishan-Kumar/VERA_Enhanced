"use client"

import { BarChart3, FileText, Home, MessageSquare, Search } from "lucide-react"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import { apiPage } from "@/lib/api"
import type { Product } from "@/lib/types"

const pages = [
  { href: "/", label: "Analyze a review", icon: Home },
  { href: "/products", label: "View rankings", icon: BarChart3 },
  { href: "/advisor", label: "Product Advisor & RAG Recommendations", icon: Search },
  { href: "/chat", label: "AI Audio Buyer Chatbot", icon: MessageSquare },
  { href: "/insights", label: "Insights & Comparative Study", icon: BarChart3 },
  { href: "/about", label: "Read methodology", icon: FileText },
]

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const router = useRouter()
  const [products, setProducts] = useState<Product[]>([])

  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    apiPage<Product>("/products?limit=50&offset=0", { signal: controller.signal })
      .then(({ items }) => setProducts(items))
      .catch(() => undefined)
    return () => controller.abort()
  }, [open])

  function navigate(href: string) {
    onOpenChange(false)
    router.push(href)
  }

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} title="Navigate VERA" description="Jump to a page or a product from the current rankings page." className="border-border bg-card shadow-[var(--shadow-elevated)]">
      <CommandInput placeholder="Search pages, product title, or ASIN..." />
      <CommandList>
        <CommandEmpty>No matching page or loaded product.</CommandEmpty>
        <CommandGroup heading="Navigate">
          {pages.map(({ href, label, icon: Icon }) => (
            <CommandItem key={href} value={label} onSelect={() => navigate(href)} className="min-h-11">
              <Icon strokeWidth={1.5} />{label}
            </CommandItem>
          ))}
        </CommandGroup>
        {products.length > 0 && <>
          <CommandSeparator />
          <CommandGroup heading="Products on the current page">
            {products.map((product) => (
              <CommandItem key={product.asin} value={`${product.title ?? "Untitled product"} ${product.asin}`} onSelect={() => navigate(`/products/${encodeURIComponent(product.asin)}`)} className="min-h-11">
                <Search strokeWidth={1.5} />
                <span className="truncate">{product.title ?? "Untitled product"}</span>
                <CommandShortcut className="font-mono">{product.asin}</CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>
        </>}
      </CommandList>
    </CommandDialog>
  )
}
