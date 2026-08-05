import { test, expect } from "@playwright/test";

// R16 (rev40) 关键流程烟测. 仅校验页面骨架 + a11y label/role 能定位, 不跑完整业务流.
// 网络层用 page.route 拦截, 不依赖后端. 跑: npm run test:e2e (需先启 npm run dev).

test.describe("首页骨架 (smoke)", () => {
  test("loads nav + footer + h1 + Flask Studio 链接", async ({ page }) => {
    await page.route("**/api/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
    await page.goto("/");
    await expect(page.getByRole("link", { name: /Fliki Studio|本地视频制作台|Fliki 还原/ }).first()).toBeVisible();
    await expect(page.locator("footer")).toBeVisible();
  });
});

test.describe("登录页 (smoke)", () => {
  test("邮箱 + 密码 inputs 通过 htmlFor label 命中 (a11y 守门)", async ({ page }) => {
    await page.route("**/api/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "{}" }));
    await page.goto("/login.html");
    await expect(page.getByLabel("邮箱")).toBeVisible();
    await expect(page.getByLabel("密码")).toBeVisible();
    await expect(page.getByRole("button", { name: /登录/ })).toBeVisible();
  });

  test("空表单提交 -> 错误提示 (no network call)", async ({ page }) => {
    let postCalls = 0;
    await page.route("**/api/**", (route) => {
      if (route.request().method() === "POST") postCalls++;
      return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });
    await page.goto("/login.html");
    await page.getByRole("button", { name: /登录/ }).click();
    await expect(page.getByText(/请输入邮箱和密码/)).toBeVisible();
    expect(postCalls).toBe(0);
  });
});

test.describe("注册页 (smoke)", () => {
  test("3 inputs + 提交按钮 + 登录链接", async ({ page }) => {
    await page.route("**/api/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "{}" }));
    await page.goto("/signup.html");
    await expect(page.getByLabel("邮箱")).toBeVisible();
    await expect(page.getByLabel(/密码/)).toBeVisible();
    await expect(page.getByLabel("确认密码")).toBeVisible();
    await expect(page.getByRole("button", { name: /免费注册|注册/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /登录/ })).toBeVisible();
  });
});

test.describe("Billing 页 (smoke)", () => {
  test("4 plans 标题 + subscribe 按钮 aria-label", async ({ page }) => {
    await page.route("**/billing/plans", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          plans: [
            { id: "free", name: "Free", monthly_credits: 50, price_monthly: 0, price_yearly: 0 },
            { id: "standard", name: "Standard", monthly_credits: 500, price_monthly: 12, price_yearly: 120 },
            { id: "premium", name: "Premium", monthly_credits: 2000, price_monthly: 39, price_yearly: 390 },
            { id: "enterprise", name: "Enterprise", monthly_credits: null, price_monthly: null, price_yearly: null },
          ],
        }),
      })
    );
    await page.route("**/billing/me", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ subscription: null, credits: { balance: 0, ledger: [] } }) })
    );
    await page.goto("/billing.html");
    for (const name of ["Free", "Standard", "Premium", "Enterprise"]) {
      await expect(page.getByRole("heading", { name })).toBeVisible();
    }
    await expect(page.getByRole("button", { name: /切换到 Free 套餐/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /联系销售 Enterprise 套餐/ })).toBeVisible();
  });
});
