import { defineConfig, devices } from "@playwright/test";

// Runs against the mock API served by the production build (npm run build first, or use npm run e2e).
const PORT = Number(process.env.PW_PORT ?? 3200);
export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure", ...devices["Desktop Chrome"] },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
    { name: "phone-375", use: { viewport: { width: 375, height: 740 } }, testMatch: /(smoke|app|pickers)\.spec\.ts/ },
    { name: "tablet-768", use: { viewport: { width: 768, height: 900 } }, testMatch: /(smoke|app)\.spec\.ts/ },
  ],
  webServer: {
    command: `npx next start -p ${PORT}`,
    env: { NEXT_DIST: process.env.NEXT_DIST ?? ".next" },
    url: `http://localhost:${PORT}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
