import type { Metadata } from "next";
import { ProductDetail } from "@/components/ProductDetail";

type Props = { params: Promise<{ asin: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { asin } = await params;
  return { title: `Product ${decodeURIComponent(asin)}` };
}

export default async function ProductPage({ params }: Props) {
  const { asin } = await params;
  return <ProductDetail asin={decodeURIComponent(asin)} />;
}
