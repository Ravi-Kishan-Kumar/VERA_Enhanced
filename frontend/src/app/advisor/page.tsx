import { ProductAdvisor } from "@/components/vera/product-advisor"
import { pageMetadata } from "@/lib/metadata"

export const metadata = pageMetadata(
  "Product Advisor & RAG Recommendations",
  "Find the best earbuds or headphones based on your points of interest, price bracket, and audio preferences in India.",
  "/advisor"
)

export default function AdvisorPage() {
  return (
    <>
      <header className="page-hero grid items-end gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.6fr)]">
        <div>
          <p className="eyebrow">Intelligent Buying Guide</p>
          <h1 className="display-title mt-3 max-w-4xl">Product Advisor &amp; Match</h1>
        </div>
        <p className="max-w-xl text-base leading-7 text-muted-foreground">
          Query earbuds and headphones tailored to your priorities. Filter by audio, ANC, connectivity, or budget, and discover top-ranked recommendations in India.
        </p>
      </header>
      <ProductAdvisor />
    </>
  )
}
