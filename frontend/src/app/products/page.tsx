import { ProductRankings } from "@/components/vera/product-rankings"
import { pageMetadata } from "@/lib/metadata"

export const metadata = pageMetadata("Product rankings", "Compare earbuds using review-based experience scores, aspect sentiment, and uncertainty-aware rankings.", "/products")

export default function ProductsPage() {
  return (
    <>
      <header className="page-hero grid items-end gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(18rem,0.7fr)]">
        <div><p className="eyebrow">Product rankings</p><h1 className="display-title mt-3 max-w-4xl">Experience over clicks.</h1></div>
        <p className="max-w-xl text-base leading-7 text-muted-foreground">Compare corrected scores with visible uncertainty and cautious ranking for smaller review sets.</p>
      </header>
      <ProductRankings />
    </>
  )
}
