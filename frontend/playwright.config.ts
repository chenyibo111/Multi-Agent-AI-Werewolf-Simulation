import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";

const localChrome = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ?? (existsSync(localChrome) ? localChrome : undefined);

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  timeout: 30_000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5173",
    launchOptions: { executablePath },
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "..\\backend\\.venv\\Scripts\\python.exe scripts\\start-e2e-backend.py",
      url: "http://127.0.0.1:8000/docs",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
