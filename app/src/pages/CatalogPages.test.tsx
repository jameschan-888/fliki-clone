import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CharactersPage, FeaturesPage, UseCasesPage } from "./CatalogPages";

vi.mock("../components/layout/Footer", () => ({
  Footer: () => <footer data-testid="footer-stub" />,
}));

beforeEach(() => {
  try { localStorage.clear(); } catch {}
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { href: "", reload: vi.fn() },
  });
  vi.clearAllMocks();
});

describe("CharactersPage R19b (rev40)", () => {
  it("renders h1 + 搜索角色 input + 13 filter buttons (a11y)", () => {
    render(<CharactersPage />);
    expect(screen.getByRole("heading", { name: /让每个故事都有合适的角色/ })).toBeTruthy();
    expect(screen.getByLabelText("搜索角色")).toBeTruthy();
    const filterBtns = screen.getAllByRole("button", { name: /(全部|US|UK|Canada|Australia|Germany|France|Spain|Japan|China|Brazil|India|Singapore)/ });
    expect(filterBtns.length).toBe(13);
  });

  it("filter buttons have aria-pressed (默认 全部 selected)", () => {
    render(<CharactersPage />);
    const allBtn = screen.getByRole("button", { name: "全部" });
    expect(allBtn.getAttribute("aria-pressed")).toBe("true");
    const usBtn = screen.getByRole("button", { name: "US" });
    expect(usBtn.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(usBtn);
    expect(usBtn.getAttribute("aria-pressed")).toBe("true");
    expect(allBtn.getAttribute("aria-pressed")).toBe("false");
  });

  it("search input filters visible characters", () => {
    render(<CharactersPage />);
    const search = screen.getByLabelText("搜索角色");
    fireEvent.change(search, { target: { value: "Mia" } });
    expect(screen.getAllByText(/^Mia /).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^Alex /)).toBeNull();
  });

  it("card 使用角色 button has aria-label with character name", () => {
    render(<CharactersPage />);
    const firstCardBtn = screen.getAllByRole("button", { name: /使用角色/ })[0];
    expect(firstCardBtn.getAttribute("aria-label")).toMatch(/使用角色 /);
  });
});

describe("FeaturesPage R19b (rev40)", () => {
  it("renders h1 + 4 feature groups + nav links", () => {
    render(<FeaturesPage />);
    expect(screen.getByRole("heading", { name: /从想法到成片/ })).toBeTruthy();
    for (const groupName of ["Create", "Edit", "Publish", "AI Models"]) {
      expect(screen.getByRole("heading", { name: groupName })).toBeTruthy();
    }
  });

  it("feature link has aria-label + icon span is aria-hidden", () => {
    render(<FeaturesPage />);
    const link = screen.getByRole("link", { name: /Idea to Video.*功能详情/ });
    expect(link.getAttribute("href")).toContain("/drafts.html?feature=Idea%20to%20Video");
    const icons = link.querySelectorAll('[aria-hidden="true"]');
    expect(icons.length).toBeGreaterThanOrEqual(1);
  });
});

describe("UseCasesPage R19b (rev40)", () => {
  it("renders h1 + 8 use case cards + API banner", () => {
    render(<UseCasesPage />);
    expect(screen.getByRole("heading", { name: /每一种业务/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Marketing & Ads" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /把视频生成接入你的产品/ })).toBeTruthy();
  });

  it("use case link has aria-label + href with useCase id", () => {
    render(<UseCasesPage />);
    const link = screen.getByRole("link", { name: /查看 Marketing & Ads 工作流/ });
    expect(link.getAttribute("href")).toBe("/drafts.html?useCase=marketing");
  });

  it("API banner link points to /docs-api.html", () => {
    render(<UseCasesPage />);
    const docsLink = screen.getByRole("link", { name: /查看 API 文档/ });
    expect(docsLink.getAttribute("href")).toBe("/docs-api.html");
  });
});
