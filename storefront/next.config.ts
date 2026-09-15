import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Emits a self-contained server bundle for the Docker image.
  output: "standalone",
  eslint: {
    // Linting is a separate concern from building; `next lint` runs it in CI.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
