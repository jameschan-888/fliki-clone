// Timeline thumbnail 渲染测试: 验证 element.id 前缀 kind -> thumb src.
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { Timeline, type TimelineScene } from "./Timeline";

const scenes: TimelineScene[] = [
  { id: "s1", index: 0, duration_seconds: 10 },
  { id: "s2", index: 1, duration_seconds: 8 },
];

describe("Timeline thumbnails", () => {
  beforeEach(() => cleanup());

  it("renders timeline with default scene clips (no thumb for scene kind)", () => {
    const { container } = render(<Timeline scenes={scenes} />);
    // scene kind clips 没有 thumbnail (thumbFor 不会匹配 scene id)
    const thumbs = container.querySelectorAll('[data-testid="timeline-thumb"]');
    expect(thumbs.length).toBe(0);
  });

  it("renders thumb src for known element kinds", () => {
    const win = window as any;
    // inject fake elements into store
    win.__editorActions.addElement({
      id: "watermark-abc",
      position: "bottom-right",
      size: 100,
      opacity: 50,
      width: 120,
      height: 60,
      x: 10,
      y: 600,
    });
    win.__editorActions.addElement({
      id: "logo-xyz",
      position: "top-left",
      size: 80,
      opacity: 100,
      width: 100,
      height: 80,
      x: 20,
      y: 20,
    });
    const { container } = render(<Timeline scenes={scenes} />);
    const thumbs = container.querySelectorAll('[data-testid="timeline-thumb"]');
    expect(thumbs.length).toBe(2);
    const srcs = Array.from(thumbs).map((n) => (n as HTMLImageElement).src);
    expect(srcs.some((s) => s.includes("/fliki-assets/series/ep1.webp"))).toBe(true);
    expect(srcs.some((s) => s.includes("/fliki-assets/testimonials/rachel.webp"))).toBe(true);
    // cleanup store
    win.__editorActions.reset();
  });

  it("returns null for unknown kind (no thumb)", () => {
    const win = window as any;
    win.__editorActions.addElement({
      id: "unknown-foo",
      position: "center",
      size: 100,
      opacity: 100,
      width: 50,
      height: 50,
      x: 100,
      y: 100,
    });
    const { container } = render(<Timeline scenes={scenes} />);
    const thumbs = container.querySelectorAll('[data-testid="timeline-thumb"]');
    expect(thumbs.length).toBe(0);
    win.__editorActions.reset();
  });
});
