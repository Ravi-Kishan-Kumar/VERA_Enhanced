import type { Metadata } from "next";

export const siteUrl = new URL(process.env.SITE_URL || "http://localhost:3000");
if (!["https:", "http:"].includes(siteUrl.protocol) || siteUrl.username || siteUrl.password || siteUrl.pathname !== "/" || siteUrl.search || siteUrl.hash) {
  throw new Error("SITE_URL must be an HTTP(S) origin without credentials, path, query, or fragment.");
}

export function pageMetadata(title: string, description: string, path?: string): Metadata {
  return {
    title,
    description,
    ...(path ? { alternates: { canonical: path } } : {}),
    openGraph: { title, description, siteName: "VERA", type: "website", locale: "en_US", ...(path ? { url: path } : {}) },
    twitter: { card: "summary_large_image", title, description },
  };
}
