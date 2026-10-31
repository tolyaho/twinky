import { defineConfig, devices } from "@playwright/test";

const PORT = 4280;
// PW_BASE_URL lets the real-network smoke run against a DEPLOYED url instead of the local preview.
const externalBase = process.env.PW_BASE_URL;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: externalBase ?? `http://localhost:${PORT}`,
    trace: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    // Safari's engine runs the topic model differently (no cross-origin isolation, so no threads)
    { name: "webkit", use: { ...devices["Desktop Safari"] }, testMatch: /semantic\.spec\.ts/ },
  ],
  webServer: externalBase
    ? undefined
    : {
        command: `npm run preview -- --port ${PORT} --strictPort`,
        port: PORT,
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
