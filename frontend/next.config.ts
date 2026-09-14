import type { NextConfig } from "next";

const backend = new URL(process.env.API_URL || "http://127.0.0.1:8000");
if (!["http:", "https:"].includes(backend.protocol) || backend.username || backend.password || backend.pathname !== "/" || backend.search || backend.hash) {
  throw new Error("API_URL must be an HTTP(S) origin without credentials, path, query, or fragment.");
}

const config: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  // Bound prerender concurrency on the shared development/training machine.
  experimental: { cpus: 1 },
  async rewrites() {
    return [
      { source: "/api/ready", destination: `${backend.origin}/ready` },
      { source: "/api/:path*", destination: `${backend.origin}/api/:path*` },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ] }];
  },
};
export default config;
