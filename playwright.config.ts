import { defineConfig } from "@playwright/test";
import { BACKEND, BACKEND_PORT, DASHBOARD_PORT, DATABASE } from "./e2e/where";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  use: { baseURL: `http://localhost:${String(DASHBOARD_PORT)}` },
  webServer: [
    {
      command: `node e2e/reset.mjs && uv run -m uvicorn backend.main:app --port ${String(BACKEND_PORT)}`,
      url: `${BACKEND}/api/health`,
      env: { UNDERCOVER_DB: DATABASE },
    },
    {
      command: `npx vite dashboard --port ${String(DASHBOARD_PORT)} --strictPort`,
      url: `http://localhost:${String(DASHBOARD_PORT)}`,
      env: { BACKEND_URL: BACKEND },
    },
  ],
});
