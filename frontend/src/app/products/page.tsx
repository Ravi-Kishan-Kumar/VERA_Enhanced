import { pageMetadata } from "@/lib/metadata";
import { ProductTable } from "@/components/ProductTable";

export const metadata = pageMetadata("Product rankings", "Compare earbuds using review-based experience scores, aspect sentiment, and uncertainty-aware rankings.", "/products");

export default function ProductsPage() {
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow"><span className="tiny-square" aria-hidden="true" /> PRODUCT RANKINGS</div>
        <h1>Ranked by experience, not clicks.</h1>
        <p>
          Scores account for review quality and uncertainty. Small or noisy review sets are pulled
          toward the population mean, so a star average is only part of the picture.
        </p>
      </div>
      <ProductTable />
    </>
  );
}
