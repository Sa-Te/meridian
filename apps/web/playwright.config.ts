import { defineConfig, devices } from "@playwright/test";

/** No `webServer` block: on this host, `next dev`/`next build` fail under
 * Turbopack because apps/web/node_modules is a symlink onto a different
 * filesystem (a WSL performance workaround, unrelated to this project) --
 * see docs/adr/0014. Playwright instead targets an already-running stack
 * (docker compose up), which builds and runs Next.js inside a container
 * where node_modules is a normal directory, unaffected by that symlink. */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  reporter: "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3001",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
