import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Vitest config for desk-ui.
 *
 * Keeps the path alias in sync with tsconfig (`@/*` -> `src/*`) so tests can
 * import feature code the same way app code does. Runs in jsdom with a global
 * setup file that pulls in jest-dom matchers + common Next.js mocks.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
