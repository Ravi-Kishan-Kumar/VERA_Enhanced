import type { Metadata } from "next";
import { ProductDetail } from "@/components/vera/product-detail";
import { pageMetadata } from "@/lib/metadata";

type Props = { params: Promise<{ asin: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { asin } = await params;
  return pageMetadata(`Product ${asin}`, "Explore this earbud product's experience score, uncertainty, aspect breakdown, and analyzed reviews.", `/products/${encodeURIComponent(asin)}`);
}

export default async function ProductPage({ params }: Props) {
  const { asin } = await params;
  return <ProductDetail asin={asin} />;
}
