import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Next.js resolves the tsconfig "@/*" alias itself; Vitest runs on
    // plain Vite, which doesn't read tsconfig paths automatically.
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // e2e/ holds Playwright specs (playwright.config.ts), not Vitest ones --
    // both use a *.spec.ts naming convention, so Vitest's default include
    // glob would otherwise try to run them too.
    exclude: ["**/node_modules/**", "**/e2e/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["app/**/*.{ts,tsx}"],
      exclude: [
        "app/**/*.test.{ts,tsx}",
        "app/**/*.d.ts",
        "app/layout.tsx",
        "app/**/page.tsx",
        // Pure type declarations -- nothing to execute, so coverage on this
        // file is meaningless (unlike client.ts's runtime logic).
        "app/lib/api/types.ts",
      ],
    },
  },
});
