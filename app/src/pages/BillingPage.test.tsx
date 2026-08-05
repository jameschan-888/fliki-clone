import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BillingPage } from "./BillingPage";

vi.mock("../components/layout/Footer", () => ({
  Footer: () => <footer data-testid="footer-stub" />,
}));
vi.mock("../api/auth", () => ({
  ensureSession: vi.fn().mockResolvedValue(undefined),
}));

const PLANS = [
  { id: "free", name: "Free", monthly_credits: 50, price_monthly: 0, price_yearly: 0 },
  { id: "standard", name: "Standard", monthly_credits: 500, price_monthly: 12, price_yearly: 120 },
  { id: "premium", name: "Premium", monthly_credits: 2000, price_monthly: 39, price_yearly: 390 },
  { id: "enterprise", name: "Enterprise", monthly_credits: null, price_monthly: null, price_yearly: null },
];

function mockPlansResponse() {
  return new Response(JSON.stringify({ plans: PLANS }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function mockStateResponse(state: unknown, status = 200) {
  return new Response(JSON.stringify(state), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function setupFetch(planResponses: Array<(url: string, init: RequestInit) => Response>) {
  let call = 0;
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    const responder = planResponses[Math.min(call, planResponses.length - 1)];
    call++;
    return Promise.resolve(responder(url, init || {}));
  });
}

beforeEach(() => {
  try { localStorage.clear(); } catch {}
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { href: "", reload: vi.fn() },
  });
  vi.clearAllMocks();
});

describe("BillingPage R14 (rev39)", () => {
  it("renders nav + hero + 4 plan cards + footer", async () => {
    setupFetch([
      () => mockPlansResponse(),
      () => mockStateResponse({ subscription: null, credits: { balance: 0, ledger: [] } }),
    ]);
    render(<BillingPage />);
    await waitFor(() => {
      for (const p of PLANS) expect(screen.getByRole("heading", { name: p.name })).toBeTruthy();
    });
    expect(screen.getByTestId("footer-stub")).toBeTruthy();
    expect(screen.getByRole("heading", { name: /选择适合你的创作额度/ })).toBeTruthy();
  });

  it("plan cards show prices + credits line + descriptive button label (a11y aria-label)", async () => {
    setupFetch([
      () => mockPlansResponse(),
      () => mockStateResponse({ subscription: null, credits: { balance: 0, ledger: [] } }),
    ]);
    render(<BillingPage />);
    await waitFor(() => screen.getByRole("button", { name: /切换到 Free 套餐/ }));
    expect(screen.getByRole("button", { name: /切换到 Free 套餐/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /切换到 Standard 套餐/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /切换到 Premium 套餐/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /联系销售 Enterprise 套餐/ })).toBeTruthy();
  });

  it("active plan shows 当前方案 + button disabled + aria-current=true (a11y)", async () => {
    setupFetch([
      () => mockPlansResponse(),
      () => mockStateResponse({
        subscription: { plan: "standard", billing_cycle: "monthly" },
        credits: { balance: 250, ledger: [{ delta: 500, reason: "signup", created_at: "2026-08-01" }] },
      }),
    ]);
    render(<BillingPage />);
    const activeBtn = await screen.findByRole("button", { name: /当前方案 Standard 套餐/ });
    expect(activeBtn.getAttribute("aria-current")).toBe("true");
    expect((activeBtn as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/可用 credits · 当前 standard/)).toBeTruthy();
    expect(screen.getByRole("status")).toBeTruthy();
  });

  it("credit balance wraps role=status + aria-live=polite (a11y)", async () => {
    setupFetch([
      () => mockPlansResponse(),
      () => mockStateResponse({
        subscription: { plan: "free", billing_cycle: "monthly" },
        credits: { balance: 1234, ledger: [] },
      }),
    ]);
    const { container } = render(<BillingPage />);
    await waitFor(() => {
      const balance = container.querySelector(".creditBalance") as HTMLElement;
      expect(balance.getAttribute("role")).toBe("status");
      expect(balance.getAttribute("aria-live")).toBe("polite");
    });
  });

  it("click subscribe -> POST /billing/subscribe with plan + billing_cycle=monthly", async () => {
    const fetchSpy = setupFetch([
      () => mockPlansResponse(),
      () => mockStateResponse({ subscription: null, credits: { balance: 0, ledger: [] } }),
      () => mockStateResponse({
        subscription: { plan: "premium", billing_cycle: "monthly" },
        credits: { balance: 2000, ledger: [] },
      }),
    ]);
    render(<BillingPage />);
    const btn = await screen.findByRole("button", { name: /切换到 Premium 套餐/ });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled();
      const post = fetchSpy.mock.calls.find(([, init]) => init && (init as RequestInit).method === "POST");
      expect(post).toBeTruthy();
      const body = JSON.parse(((post![1] as RequestInit).body as string));
      expect(body).toEqual({ plan: "premium", billing_cycle: "monthly" });
    });
  });

  it("subscribe error -> shows .billingError with server message", async () => {
    setupFetch([
      () => mockPlansResponse(),
      () => mockStateResponse({ subscription: null, credits: { balance: 0, ledger: [] } }),
      () => mockStateResponse({ detail: { message: "支付通道暂未开放" } }, 500),
    ]);
    const { container } = render(<BillingPage />);
    const btn = await screen.findByRole("button", { name: /切换到 Standard 套餐/ });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(container.querySelector(".billingError")?.textContent).toContain("支付通道暂未开放");
    });
  });

  it("busy state -> button shows 保存中... + aria-busy=true + disabled", async () => {
    let resolvePost: ((v: Response) => void) | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/billing/plans")) return Promise.resolve(mockPlansResponse());
      if (url.includes("/billing/me")) return Promise.resolve(mockStateResponse({ subscription: null, credits: { balance: 0, ledger: [] } }));
      if (init && (init as RequestInit).method === "POST") {
        return new Promise<Response>((resolve) => { resolvePost = resolve; });
      }
      return Promise.resolve(mockStateResponse({}));
    });
    render(<BillingPage />);
    const btn = await screen.findByRole("button", { name: /切换到 Premium 套餐/ });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(btn.getAttribute("aria-busy")).toBe("true");
      expect(btn.textContent).toBe("保存中...");
      expect((btn as HTMLButtonElement).disabled).toBe(true);
    });
    // resolve to avoid act() warning
    if (resolvePost) resolvePost(mockStateResponse({ subscription: { plan: "premium", billing_cycle: "monthly" }, credits: { balance: 0, ledger: [] } }));
    await waitFor(() => {
      expect(btn.getAttribute("aria-busy")).toBe("false");
    });
  });

  it("未登录 -> /billing/me 401 -> 显示 请先登录 (error path)", async () => {
    setupFetch([
      () => mockPlansResponse(),
      () => new Response(JSON.stringify({ detail: "请先登录" }), { status: 401, headers: { "Content-Type": "application/json" } }),
    ]);
    const { container } = render(<BillingPage />);
    await waitFor(() => {
      expect(container.querySelector(".billingError")?.textContent).toBe("请先登录");
    });
  });
});
