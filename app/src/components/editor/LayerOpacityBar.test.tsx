// LayerOpacityBar drag 测试: pointer 拖动改 opacity, mouseup 时 commit onChange.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { LayerOpacityBar } from "./LayerOpacityBar";

function firePointer(el: Element, type: string, init: { clientX: number; pointerId?: number }) {
  el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, ...init }));
}

describe("LayerOpacityBar drag", () => {
  beforeEach(() => cleanup());

  it("renders 60x8 bar with fill width = opacity%", () => {
    render(<LayerOpacityBar layerId="l1" opacity={75} fillColor="#5b6cff" onChange={() => {}} />);
    const bar = screen.getByTestId("layer-opacity-bar-l1") as HTMLElement;
    expect(bar.style.width).toBe("60px");
    expect(bar.style.height).toBe("8px");
    const fill = screen.getByTestId("layer-opacity-fill-l1") as HTMLElement;
    expect(fill.style.width).toBe("75%");
  });

  it("shows opacity% text overlay", () => {
    render(<LayerOpacityBar layerId="l1" opacity={50} fillColor="#48d58b" onChange={() => {}} />);
    expect(screen.getByTestId("layer-opacity-bar-l1").textContent).toContain("50%");
  });

  it("drag right increases opacity and commits on pointerup", () => {
    const onChange = vi.fn();
    render(<LayerOpacityBar layerId="l1" opacity={50} fillColor="#f5a524" onChange={onChange} />);
    const bar = screen.getByTestId("layer-opacity-bar-l1");
    firePointer(bar, "pointerdown", { clientX: 0 });
    firePointer(bar, "pointermove", { clientX: 30 });
    firePointer(bar, "pointerup", { clientX: 30 });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0]).toBe(100);
  });

  it("drag left decreases opacity", () => {
    const onChange = vi.fn();
    render(<LayerOpacityBar layerId="l1" opacity={80} fillColor="#19b5c5" onChange={onChange} />);
    const bar = screen.getByTestId("layer-opacity-bar-l1");
    firePointer(bar, "pointerdown", { clientX: 60 });
    firePointer(bar, "pointermove", { clientX: 30 });
    firePointer(bar, "pointerup", { clientX: 30 });
    expect(onChange.mock.calls[0][0]).toBe(30);
  });

  it("clamps opacity to [0, 100]", () => {
    const onChange = vi.fn();
    render(<LayerOpacityBar layerId="l1" opacity={50} fillColor="#5b6cff" onChange={onChange} />);
    const bar = screen.getByTestId("layer-opacity-bar-l1");
    firePointer(bar, "pointerdown", { clientX: 0 });
    firePointer(bar, "pointermove", { clientX: -1000 });
    firePointer(bar, "pointerup", { clientX: -1000 });
    expect(onChange.mock.calls[0][0]).toBe(0);
  });

  it("does not commit if pointerup without move", () => {
    const onChange = vi.fn();
    render(<LayerOpacityBar layerId="l1" opacity={50} fillColor="#5b6cff" onChange={onChange} />);
    const bar = screen.getByTestId("layer-opacity-bar-l1");
    firePointer(bar, "pointerdown", { clientX: 0 });
    firePointer(bar, "pointerup", { clientX: 0 });
    expect(onChange).not.toHaveBeenCalled();
  });
});
