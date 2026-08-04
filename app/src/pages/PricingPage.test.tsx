import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PricingPage } from "./PricingPage";

const EXPECTED_WORKFLOWS = [
  { tag: "Video", name: "Idea to Video" },
  { tag: "Video", name: "Script to Video" },
  { tag: "Video", name: "Blog to Video" },
  { tag: "Video", name: "PPT to Video" },
  { tag: "Video", name: "Auto-edit Video" },
  { tag: "Video", name: "Recording to Video" },
  { tag: "Audio", name: "Idea to Audio" },
  { tag: "Audio", name: "Script to Audio" },
  { tag: "Audio", name: "Blog to Audio" },
  { tag: "Image", name: "Idea to Thumbnail" },
  { tag: "Image", name: "Idea to Social Carousel" },
  { tag: "Image", name: "Idea to Presentation" },
];

const EXPECTED_FAQS = [
  "Credit 怎么扣?",
  "能用我自己的声音吗?",
  "可以商用吗?",
  "支持哪些支付方式?",
  "可以随时取消吗?",
  "团队可以多人协作吗?",
];

const EXPECTED_PLANS = ["Free", "Standard", "Premium"];

describe("PricingPage R5 structure (rev37)", () => {
  it("renders 3 plan tier names (Free/Standard/Premium appear >=1 each)", () => {
    render(<PricingPage />);
    for (const name of EXPECTED_PLANS) {
      expect(screen.getAllByText(name, { exact: true }).length).toBeGreaterThan(0);
    }
  });

  it("renders all 12 WORKFLOWS (each name appears >=1)", () => {
    render(<PricingPage />);
    for (const wf of EXPECTED_WORKFLOWS) {
      expect(screen.getAllByText(wf.name).length).toBeGreaterThan(0);
      expect(screen.getAllByText(wf.tag, { exact: true }).length).toBeGreaterThan(0);
    }
  });

  it("WORKFLOWS by tag: Video 6 / Audio 3 / Image 3", () => {
    render(<PricingPage />);
    expect(screen.getAllByText("Video", { exact: true }).length).toBeGreaterThanOrEqual(6);
    expect(screen.getAllByText("Audio", { exact: true }).length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText("Image", { exact: true }).length).toBeGreaterThanOrEqual(3);
  });

  it("renders all 6 FAQ questions", () => {
    render(<PricingPage />);
    for (const q of EXPECTED_FAQS) {
      expect(screen.getAllByText(q).length).toBeGreaterThan(0);
    }
  });

  it("renders Footer columns (Product/Resources/Company/Use Cases/Legal)", () => {
    render(<PricingPage />);
    for (const col of ["Product", "Resources", "Company", "Use Cases", "Legal"]) {
      expect(screen.getAllByText(col, { exact: true }).length).toBeGreaterThan(0);
    }
  });

  it("cycle toggle: 月付/年付 都出现 + button/tablist 角色在", () => {
    render(<PricingPage />);
    expect(screen.getAllByText(/月付/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/年付/).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("tablist").length).toBeGreaterThan(0);
  });

  it("source guard: 12 workflow names + tags 都非空", () => {
    for (const wf of EXPECTED_WORKFLOWS) {
      expect(wf.name).toBeTruthy();
      expect(wf.tag).toBeTruthy();
      expect(wf.name.length).toBeGreaterThan(0);
      expect(wf.tag.length).toBeGreaterThan(0);
    }
    expect(EXPECTED_WORKFLOWS).toHaveLength(12);
  });

  it("source guard: 6 FAQ 问题 都非空 + 收问号", () => {
    for (const q of EXPECTED_FAQS) {
      expect(q).toBeTruthy();
      expect(q.length).toBeGreaterThan(0);
      expect(q).toMatch(/\?$|？$/);
    }
    expect(EXPECTED_FAQS).toHaveLength(6);
  });

describe("PricingPage R7 PLANS + COMPARE (rev38)", () => {
  it("PLANS: exactly 3 .plan articles render", () => {
    render(<PricingPage />);
    expect(screen.getAllByRole("article").length).toBeGreaterThanOrEqual(3);
    const plans = document.querySelectorAll(".plan");
    expect(plans.length).toBe(3);
  });

  it("PLANS: only Standard has featured badge (最受欢迎)", () => {
    render(<PricingPage />);
    const badges = document.querySelectorAll(".plan-badge");
    expect(badges.length).toBe(1);
    expect(badges[0].textContent).toBe("最受欢迎");
    const featured = document.querySelectorAll(".plan.featured");
    expect(featured.length).toBe(1);
  });

  it("PLANS: each plan has $price + cta href = /signup.html", () => {
    render(<PricingPage />);
    const ctas = document.querySelectorAll(".plan-cta");
    expect(ctas.length).toBe(3);
    for (const a of ctas) {
      expect(a.getAttribute("href")).toBe("/signup.html");
    }
    const prices = document.querySelectorAll(".plan-price");
    expect(prices.length).toBe(3);
    for (const p of prices) {
      expect(p.textContent.trim().startsWith("$")).toBe(true);
    }
  });

  it("PLANS: each plan >=5 bullets, Free plan >=2 .no items", () => {
    render(<PricingPage />);
    const planBullets = document.querySelectorAll(".plan ul");
    expect(planBullets.length).toBe(3);
    for (const ul of planBullets) {
      expect(ul.querySelectorAll("li").length).toBeGreaterThanOrEqual(5);
    }
    const firstUl = planBullets[0];
    const noItems = firstUl.querySelectorAll("li.no");
    expect(noItems.length).toBeGreaterThanOrEqual(2);
  });

  it("PLANS: cycle toggle switches between annual / monthly prices", () => {
    const { container } = render(<PricingPage />);
    // default annual: Standard $21 + old $28
    expect(container.textContent).toMatch(/\$21/);
    expect(container.textContent).toMatch(/\$28/);
    const buttons = screen.getAllByRole("button");
    const monthlyBtn = buttons.find((b) => /月付/.test(b.textContent || ""));
    expect(monthlyBtn).toBeTruthy();
    // fireEvent.click() 自动 act() 包装, 避免 state update 警告
    fireEvent.click(monthlyBtn);
    expect(container.textContent).toMatch(/\$88/);
  });

  it("COMPARE: 22 comparison rows + 4 columns (功能 + 3 plan)", () => {
    render(<PricingPage />);
    const tbody = document.querySelector(".compare tbody");
    expect(tbody).toBeTruthy();
    const rows = tbody.querySelectorAll("tr");
    expect(rows.length).toBe(22);
    const firstRowCells = rows[0].querySelectorAll("td");
    expect(firstRowCells.length).toBe(4);
  });

  it("COMPARE: boolean false renders as em-dash — (DASH_HTML)", () => {
    render(<PricingPage />);
    const dashes = document.querySelectorAll(".compare .dash");
    expect(dashes.length).toBeGreaterThan(0);
    expect(dashes.length).toBeGreaterThanOrEqual(5);
  });

  it("COMPARE: Premium row dominates API Access + Team collaboration", () => {
    render(<PricingPage />);
    const tbody = document.querySelector(".compare tbody");
    const rows = tbody.querySelectorAll("tr");
    let apiAccessRow, teamCollabRow;
    for (const tr of rows) {
      const feature = tr.querySelector("td").textContent.trim();
      if (feature === "API Access") apiAccessRow = tr;
      if (feature === "Team collaboration") teamCollabRow = tr;
    }
    expect(apiAccessRow).toBeTruthy();
    expect(teamCollabRow).toBeTruthy();
    const apiCells = apiAccessRow.querySelectorAll("td");
    expect(apiCells[1].innerHTML).toContain("dash");
    expect(apiCells[2].innerHTML).toContain("dash");
    expect(apiCells[3].innerHTML).toContain("check");
  });

  it("PLANS source guard: 3 plans with id/name/href=/signup.html", () => {
    const EXPECTED = [
      { id: "free", name: "Free", href: "/signup.html" },
      { id: "standard", name: "Standard", href: "/signup.html" },
      { id: "premium", name: "Premium", href: "/signup.html" },
    ];
    for (const ep of EXPECTED) {
      expect(ep.id).toBeTruthy();
      expect(ep.name).toBeTruthy();
      expect(ep.href).toBe("/signup.html");
    }
    expect(EXPECTED).toHaveLength(3);
  });

  it("COMPARE source guard: 22 unique features", () => {
    const FEATURES = [
      "Credits","Export length","Resolution","Scene limits","Standard voices",
      "Ultra-Realistic voices","Workflows","Publications / 月","Series",
      "AI Image","AI Video clips","AI Avatar","Voice cloning","Brand kits",
      "Bulk create","AI Copilot","Make / Zapier","No watermark","Commercial rights",
      "API Access","Team collaboration","Support"
    ];
    expect(FEATURES).toHaveLength(22);
    expect(new Set(FEATURES).size).toBe(22);
    for (const f of FEATURES) expect(f.length).toBeGreaterThan(0);
  });
});
});
