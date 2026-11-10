import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  globalTimeout: 10 * 60 * 1000,
  retries: 0,
  timeout: 90000,
  expect: { timeout: 15000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
  ],
  webServer: [
    {
      command:
        "uv run uvicorn indexpilot.main:app --host 127.0.0.1 --port 8010",
      cwd: "..",
      url: "http://127.0.0.1:8010/health/ready",
      reuseExistingServer: false,
      timeout: 30000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: "npm run dev -- --port 5174",
      url: "http://127.0.0.1:5174",
      env: { INDEXPILOT_API_TARGET: "http://127.0.0.1:8010" },
      reuseExistingServer: false,
      timeout: 30000,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
});
