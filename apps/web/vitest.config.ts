import { defineConfig } from "vitest/config";

// Minimal unit-test setup: node environment, pure-function tests only
// (no jsdom/RTL — component testing can be added when a phase needs it).
export default defineConfig({
  test: {
    environment: "node",
    include: ["**/*.test.ts"],
  },
});
