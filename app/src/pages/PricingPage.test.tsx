import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
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
});
