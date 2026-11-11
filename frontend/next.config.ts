import type { NextConfig } from "next";

const API_ORIGIN = process.env.SOURCEATLAS_API_ORIGIN ?? "http://127.0.0.1:8112";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
  turbopack: { rules: { "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" } } },
};

export default nextConfig;
