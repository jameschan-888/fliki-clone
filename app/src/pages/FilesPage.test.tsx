import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FilesPage } from "./FilesPage";

vi.mock("../components/layout/Footer", () => ({
  Footer: () => <footer data-testid="footer-stub" />,
}));

beforeEach(() => {
  try { localStorage.clear(); } catch {}
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { href: "", reload: vi.fn(), origin: "http://localhost" },
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.clearAllMocks();
});

function mockJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function setupInitialLoad(opts: { drafts?: unknown[]; runs?: unknown[]; voices?: unknown[]; templates?: unknown[] } = {}) {
  const drafts = opts.drafts ?? [{ id: "draft-1", title: "Script to Video", updated_at: new Date().toISOString(), scene_count: 5, language: "zh-CN" }];
  const runs = opts.runs ?? [{ run_id: "run-1", title: "Autoedit cut", updated_at: new Date().toISOString(), status: "done", duration_seconds: 30 }];
  const voices = opts.voices ?? [{ uuid: "voice-1", voice_name: "Voice clone", created_at: new Date(Date.now() - 86400000).toISOString(), enabled: true }];
  const templates = opts.templates ?? [{ slug: "tpl-1", name: "Brand kit", category: "social", aspect_ratio: "16:9" }];
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.includes("/workflow-drafts")) return Promise.resolve(mockJsonResponse(drafts));
    if (url.includes("/autoedit/runs")) return Promise.resolve(mockJsonResponse(runs));
    if (url.includes("/voice-clones")) return Promise.resolve(mockJsonResponse(voices));
    if (url.includes("/templates")) return Promise.resolve(mockJsonResponse(templates));
    if (url.includes("/share")) return Promise.resolve(mockJsonResponse({ url: "/shared/abc" }));
    return Promise.resolve(mockJsonResponse({}));
  });
}

function setupEmpty() {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.includes("/workflow-drafts") || url.includes("/autoedit/runs") || url.includes("/voice-clones") || url.includes("/templates")) return Promise.resolve(mockJsonResponse([]));
    return Promise.resolve(mockJsonResponse({}));
  });
}

describe("FilesPage R15 (rev40)", () => {
  it("renders h1, tablist, search input with label (a11y)", async () => {
    setupInitialLoad();
    render(<FilesPage />);
    expect(screen.getByRole("heading", { name: /我的文件/ })).toBeTruthy();
    expect(screen.getByRole("tablist", { name: /文件分类/ })).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByLabelText("搜索文件名")).toBeTruthy();
      expect((screen.getByLabelText("搜索文件名") as HTMLInputElement).type).toBe("search");
    });
  });

  it("tablist has 5 tabs with role=tab + aria-selected (default 全部 selected)", async () => {
    setupInitialLoad();
    render(<FilesPage />);
    await waitFor(() => screen.getAllByRole("tab").length >= 5);
    const tabs = screen.getAllByRole("tab");
    expect(tabs.length).toBeGreaterThanOrEqual(5);
    const selected = tabs.filter((t) => t.getAttribute("aria-selected") === "true");
    expect(selected.length).toBe(1);
    expect(selected[0].textContent).toContain("全部");
  });

  it("clicking tab updates aria-selected", async () => {
    setupInitialLoad();
    render(<FilesPage />);
    await waitFor(() => screen.getAllByRole("tab").length >= 2);
    const tabs = screen.getAllByRole("tab");
    const videoTab = tabs.find((t) => /Video/.test(t.textContent || ""));
    expect(videoTab).toBeTruthy();
    fireEvent.click(videoTab!);
    expect(videoTab!.getAttribute("aria-selected")).toBe("true");
  });

  it("view toggle has aria-pressed (grid default on)", async () => {
    setupInitialLoad();
    render(<FilesPage />);
    await waitFor(() => screen.getByRole("group", { name: /视图切换/ }));
    const gridBtn = screen.getByRole("button", { name: "网格" });
    const listBtn = screen.getByRole("button", { name: "列表" });
    expect(gridBtn.getAttribute("aria-pressed")).toBe("true");
    expect(listBtn.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(listBtn);
    expect(listBtn.getAttribute("aria-pressed")).toBe("true");
    expect(gridBtn.getAttribute("aria-pressed")).toBe("false");
  });

  it("search filter narrows visible files", async () => {
    setupInitialLoad();
    render(<FilesPage />);
    const search = await screen.findByLabelText("搜索文件名");
    fireEvent.change(search, { target: { value: "Script" } });
    await waitFor(() => {
      expect(screen.getByText("Script to Video")).toBeTruthy();
      expect(screen.queryByText("Voice clone")).toBeNull();
    });
  });

  it("check button has aria-pressed + aria-label (selecting toggles)", async () => {
    setupInitialLoad();
    render(<FilesPage />);
    await waitFor(() => screen.getByText("Script to Video"));
    const checkBtn = screen.getAllByRole("button", { name: "选择" })[0];
    expect(checkBtn.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(checkBtn);
    expect(checkBtn.getAttribute("aria-pressed")).toBe("true");
    expect(checkBtn.getAttribute("aria-label")).toBe("取消选择");
  });

  it("bulk select shows 已选 N + 批量删除/取消选择", async () => {
    setupInitialLoad();
    render(<FilesPage />);
    await waitFor(() => screen.getByText("Script to Video"));
    const checks = screen.getAllByRole("button", { name: "选择" });
    fireEvent.click(checks[0]);
    fireEvent.click(checks[1]);
    expect(screen.getByText(/已选 2/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "批量删除" })).toBeTruthy();
    const cancelBtns = screen.getAllByRole("button", { name: "取消选择" }); expect(cancelBtns.some((b) => b.classList.contains("check"))).toBe(true); expect(cancelBtns.some((b) => !b.classList.contains("check"))).toBe(true);
  });

  it("empty state -> 还没有文件 + + 新建第一个文件", async () => {
    setupEmpty();
    render(<FilesPage />);
    await waitFor(() => {
      expect(screen.getByText(/还没有文件/)).toBeTruthy();
      expect(screen.getByRole("button", { name: /\+ 新建第一个文件/ })).toBeTruthy();
    });
  });

  it("fetch error -> empty state shows (inner .catch swallows)", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.reject(new Error("network")));
    render(<FilesPage />);
    await waitFor(() => {
      expect(screen.getByText(/还没有文件/)).toBeTruthy();
    });
  });

  it("renders Footer stub", async () => {
    setupInitialLoad();
    render(<FilesPage />);
    expect(screen.getByTestId("footer-stub")).toBeTruthy();
  });
});

