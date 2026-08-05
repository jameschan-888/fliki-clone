import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { SharePage } from "./SharePage";

function mockShareResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function setupFetch(responder: (url: string) => Response) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    return Promise.resolve(responder(String(input)));
  });
}

function setupUrl(url: string) {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      get href() { return url; },
      get search() { return url.includes("?") ? "?" + url.split("?")[1] : ""; },
      get pathname() { return url.split("?")[0]; },
      reload: vi.fn(),
    },
  });
}

beforeEach(() => {
  try { localStorage.clear(); } catch {}
  vi.clearAllMocks();
});

describe("SharePage R19a (rev40)", () => {
  it("renders hero + scenes when share loads with token from query", async () => {
    setupUrl("http://localhost/share.html?token=abc123");
    setupFetch(() => mockShareResponse({
      share: {
        draft: {
          title: "My Video",
          scenes: [
            { title: "Intro", narration: "Welcome", duration_seconds: 5 },
            { title: "Body", narration: "Main content", duration_seconds: 8 },
          ],
        },
      },
    }));
    render(<SharePage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "My Video", level: 1 })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Intro", level: 2 })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Body", level: 2 })).toBeTruthy();
    });
    expect(screen.getByText("Welcome")).toBeTruthy();
    expect(screen.getByText(/5s/)).toBeTruthy();
    expect(screen.getByText(/8s/)).toBeTruthy();
  });

  it("falls back to URL path segment when no ?token query", async () => {
    setupUrl("http://localhost/share/xyz-token/");
    const spy = setupFetch(() => mockShareResponse({
      share: { draft: { title: "Path token video", scenes: [] } },
    }));
    render(<SharePage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Path token video", level: 1 })).toBeTruthy();
    });
    const calledUrl = spy.mock.calls[0][0] as string;
    expect(calledUrl).toContain("/share/xyz-token");
  });

  it("error path -> role=alert + h1 + 返回首页 link (a11y)", async () => {
    setupUrl("http://localhost/share.html?token=bad");
    setupFetch(() => mockShareResponse({ detail: { message: "分享链接已撤销" } }, 404));
    render(<SharePage />);
    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toBeTruthy();
      expect(alert.querySelector("h1")).toBeTruthy();
      expect(alert.textContent).toContain("无法打开分享");
      expect(alert.textContent).toContain("分享链接已撤销");
    });
    const back = screen.getByRole("link", { name: /返回首页/ });
    expect(back.getAttribute("href")).toBe("/index.html");
  });

  it("fetch network error -> role=alert shows generic 加载失败", async () => {
    setupUrl("http://localhost/share.html?token=abc");
    vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.reject(new Error("network")));
    render(<SharePage />);
    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain("无法打开分享");
    });
  });

  it("renders share footer link to drafts", async () => {
    setupUrl("http://localhost/share.html?token=abc");
    setupFetch(() => mockShareResponse({ share: { draft: { title: "T", scenes: [] } } }));
    render(<SharePage />);
    await waitFor(() => screen.getByRole("link", { name: /用 Fliki 创建你的视频/ }));
    expect(screen.getByRole("link", { name: /用 Fliki 创建你的视频/ }).getAttribute("href")).toBe("/drafts.html");
  });

  it("scene fallback title when scene.title empty", async () => {
    setupUrl("http://localhost/share.html?token=abc");
    setupFetch(() => mockShareResponse({
      share: {
        draft: {
          title: "T",
          scenes: [
            { title: "", narration: "X" },
            { narration: "Y" },
          ],
        },
      },
    }));
    render(<SharePage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /场景 1/, level: 2 })).toBeTruthy();
      expect(screen.getByRole("heading", { name: /场景 2/, level: 2 })).toBeTruthy();
    });
  });
});
