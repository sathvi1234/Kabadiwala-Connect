import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120000,
  use: { ...devices["Pixel 5"], baseURL: "http://127.0.0.1:4173" },
  webServer: [
    {
      command: "..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      port: 8000,
      reuseExistingServer: true,
      timeout: 120000,
    },
    {
      command: "npm run build && npm run preview -- --host 127.0.0.1 --port 4173",
      port: 4173,
      reuseExistingServer: true,
      timeout: 180000,
    },
  ],
});
