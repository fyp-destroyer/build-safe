import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Only the safety-critical pure-logic suites. Convex functions need the
    // Convex runtime and are exercised end-to-end instead.
    include: ["convex/**/*.test.ts"],
    environment: "node",
  },
});
