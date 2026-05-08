import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export only during production build; dev server needs dynamic API routes.
  ...(process.env.NODE_ENV === "production" ? { output: "export" } : {}),
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
