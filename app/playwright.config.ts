import { defineConfig, devices } from "@playwright/test";

// R16 (rev40) Playwright E2E 烟测配置.
//
// 默认 baseURL = http://127.0.0.1:5180 (Vite dev). 本地跑需先启 app (npm run dev) + backend (5181).
// CI 暂不跑 (N53 全量 pytest 已 4:31, Playwright 加 5-10min 不划算); 开发者本地启用.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5180",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
