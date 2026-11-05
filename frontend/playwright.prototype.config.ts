import { existsSync } from "node:fs";
import { defineConfig, devices } from "@playwright/test";

// The sandbox ships Chromium at a fixed path; elsewhere Playwright uses its own download.
const CHROMIUM = process.env.PW_CHROMIUM_PATH ?? (existsSync("/opt/pw-browsers/chromium") ? "/opt/pw-browsers/chromium" : undefined);

// Prototype end-to-end run: starts the S3 API locally (demo data, stub tokens) and the built app that
// forwards to it. Nothing is hosted. API host and stub tokens are passed as environment, never committed.
const WEB = Number(process.env.PROTO_WEB_PORT ?? 3300);
const API = Number(process.env.PROTO_API_PORT ?? 8792);
const env = {
  PROTOTYPE_API_URL: `http://127.0.0.1:${API}`,
  PROTOTYPE_COHORT_ID: "cohort-demo",
  PROTOTYPE_TOKENS: JSON.stringify({ teacher: "demo-teacher", "demo-a": "demo-learner-a", "demo-b": "demo-learner-b" }),
  PROTOTYPE_ROSTER: JSON.stringify([
    { id: "demo-a", label: "Learner A", origin: "DEMO FIXTURE" },
    { id: "demo-b", label: "Learner B", origin: "DEMO FIXTURE" },
    ...[1, 2, 3, 4, 5, 6].map((i) => ({ id: `sim-0${i}`, label: `Sim 0${i}`, origin: "SIM" })),
  ]),
};
export default defineConfig({
  testDir: "./e2e",
  testMatch: /prototype\.spec\.ts/,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${WEB}`, trace: "retain-on-failure", ...devices["Desktop Chrome"], launchOptions: { executablePath: CHROMIUM } },
  projects: [
    { name: "desktop", grep: /prototype path/, use: { viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 } },
    { name: "phone", grep: /phone width/, use: { viewport: { width: 375, height: 740 }, deviceScaleFactor: 2 } },
  ],
  webServer: [
    { command: `python3 e2e/api/serve_demo_api.py ${API}`, url: `http://127.0.0.1:${API}/api/prototype/health`, timeout: 60_000, reuseExistingServer: false },
    { command: `NEXT_DIST=.next-proto npx next build && NEXT_DIST=.next-proto npx next start -p ${WEB}`, url: `http://127.0.0.1:${WEB}/prototype/evaluation`, timeout: 240_000, env: { ...env } as Record<string, string>, reuseExistingServer: false },
  ],
});
