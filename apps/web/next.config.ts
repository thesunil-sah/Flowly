import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server (.next/standalone) so the Docker runtime image
  // ships only the traced production deps, not the whole pnpm store.
  output: "standalone",
  // This app lives in a pnpm monorepo; point file tracing at the repo root so
  // the standalone bundle resolves workspace-hoisted deps correctly.
  outputFileTracingRoot: path.join(__dirname, "../../"),
};

export default nextConfig;
