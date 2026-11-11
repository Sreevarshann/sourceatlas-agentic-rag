import { defineConfig, devices } from "@playwright/test";

const E2E = !process.env.SCREENSHOT_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  testMatch: E2E ? /.*\.e2e\.ts/ : /screenshots\.spec\.ts/,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: process.env.SCREENSHOT_BASE_URL ?? "http://127.0.0.1:3192", trace: "retain-on-failure", colorScheme: "light" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: E2E
    ? [
        { command: "../backend/scripts/e2e_api.sh", url: "http://127.0.0.1:8192/api/health", timeout: 240_000, reuseExistingServer: false },
        { command: "SOURCEATLAS_API_ORIGIN=http://127.0.0.1:8192 npm run build && SOURCEATLAS_API_ORIGIN=http://127.0.0.1:8192 npx next start --port 3192 --hostname 127.0.0.1", url: "http://127.0.0.1:3192", timeout: 300_000, reuseExistingServer: false },
      ]
    : undefined,
});
