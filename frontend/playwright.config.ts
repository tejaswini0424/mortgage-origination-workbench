import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
const chrome = "C:/Program Files/Google/Chrome/Application/chrome.exe";
process.env.WORKBENCH_BROWSER_DATA ||= "runtime/browser-" + Date.now();
export default defineConfig({
  testDir: "./tests",
  timeout: 60000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:18932",
    launchOptions: existsSync(chrome) ? { executablePath: chrome } : {},
  },
  webServer: [
    {
      command: "python -m uvicorn backend.app.main:app --port 18931",
      cwd: "..",
      url: "http://127.0.0.1:18931/healthz",
      env: {
        MORTGAGE_DATA: process.env.WORKBENCH_BROWSER_DATA,
        REVIEWER_PASSWORD: "browser-test-local",
        WORKBENCH_ORIGINS: "http://127.0.0.1:18932",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 18932 --strictPort",
      url: "http://127.0.0.1:18932",
      env: { MORTGAGE_API_TARGET: "http://127.0.0.1:18931" },
    },
  ],
});
