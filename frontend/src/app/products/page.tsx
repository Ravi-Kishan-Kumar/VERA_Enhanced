import type { Metadata } from "next";
import { ProductTable } from "@/components/ProductTable";

export const metadata: Metadata = { title: "Product rankings" };

export default function ProductsPage() {
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow"><span className="tiny-square" aria-hidden="true" /> PRODUCT RANKINGS</div>
        <h1>Ranked by experience, not clicks.</h1>
        <p>
          Scores are trust-weighted and shrunk toward the population mean (Empirical Bayes), so one
          glowing review cannot outrank hundreds of consistent ones.
        </p>
      </div>
      <ProductTable />
    </>
  );
}
