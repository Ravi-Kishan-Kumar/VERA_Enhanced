import { ProductRankings } from "@/components/vera/product-rankings"
import { pageMetadata } from "@/lib/metadata"

export const metadata = pageMetadata("Product rankings", "Compare earbuds using review-based experience scores, aspect sentiment, and uncertainty-aware rankings.", "/products")

export default function ProductsPage() {
  return (
    <>
      <header className="pb-12 pt-12 sm:pb-14 sm:pt-20">
        <div className="font-mono text-xs uppercase tracking-[0.16em] text-primary">Product rankings</div>
        <h1 className="mt-5 max-w-4xl text-balance text-[clamp(2.7rem,6vw,5.5rem)] font-semibold leading-[0.95] tracking-[-0.06em]">Ranked by experience, not clicks.</h1>
        <p className="mt-6 max-w-3xl text-pretty text-base leading-7 text-muted-foreground">Compare corrected experience scores with their uncertainty. Smaller or noisier review sets are pulled toward the population mean, so the ranking stays appropriately cautious.</p>
      </header>
      <ProductRankings />
    </>
  )
}
