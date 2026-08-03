// CanvasOverlay drag-resize pointer gesture 测试.
// jsdom PointerEvent 不传 clientX, 用 new PointerEvent + dispatchEvent 保证 clientX/clientY/pointerId.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { CanvasOverlay } from "./CanvasOverlay";

const baseEl = { id: "e1", x: 100, y: 100, width: 200, height: 150 };

function firePointer(el: Element, type: string, init: { clientX: number; clientY: number; pointerId: number }) {
  el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, ...init }));
}

describe("CanvasOverlay drag-resize", () => {
  beforeEach(() => cleanup());

  it("renders 320x180 canvas (1280x720 @ 0.25 scale) with element at correct pos", () => {
    render(<CanvasOverlay element={baseEl} onChange={() => {}} />);
    const overlay = screen.getByTestId("canvas-overlay") as HTMLElement;
    expect(overlay.style.width).toBe("320px");
    expect(overlay.style.height).toBe("180px");
    const el = screen.getByTestId("canvas-element") as HTMLElement;
    expect(el.style.left).toBe("25px");
    expect(el.style.top).toBe("25px");
    expect(el.style.width).toBe("50px");
    expect(el.style.height).toBe("37.5px");
  });

  it("readout shows pixel dimensions", () => {
    render(<CanvasOverlay element={baseEl} onChange={() => {}} />);
    expect(screen.getByTestId("canvas-readout").textContent).toMatch(/200x150 @ .100.100./);
  });

  it("drag center: pointerdown + move + up commits new x/y", () => {
    const onChange = vi.fn();
    render(<CanvasOverlay element={baseEl} scale={0.25} onChange={onChange} />);
    const el = screen.getByTestId("canvas-element");
    firePointer(el, "pointerdown", { clientX: 50, clientY: 50, pointerId: 1 });
    firePointer(el, "pointermove", { clientX: 80, clientY: 70, pointerId: 1 });
    firePointer(el, "pointerup", { clientX: 80, clientY: 70, pointerId: 1 });
    expect(onChange).toHaveBeenCalledTimes(1);
    const geom = onChange.mock.calls[0][0];
    expect(geom.x).toBe(220);
    expect(geom.y).toBe(180);
  });

  it("drag SE handle changes width/height only", () => {
    const onChange = vi.fn();
    render(<CanvasOverlay element={baseEl} scale={0.25} onChange={onChange} />);
    const se = screen.getByTestId("handle-se");
    firePointer(se, "pointerdown", { clientX: 100, clientY: 100, pointerId: 2 });
    firePointer(se, "pointermove", { clientX: 120, clientY: 110, pointerId: 2 });
    firePointer(se, "pointerup", { clientX: 120, clientY: 110, pointerId: 2 });
    expect(onChange).toHaveBeenCalledTimes(1);
    const geom = onChange.mock.calls[0][0];
    expect(geom.width).toBe(280);
    expect(geom.height).toBe(190);
    expect(geom.x).toBe(100);
    expect(geom.y).toBe(100);
  });

  it("clamps x to [0, 1280-width] when dragging past right edge", () => {
    const onChange = vi.fn();
    render(<CanvasOverlay element={baseEl} scale={0.25} onChange={onChange} />);
    const el = screen.getByTestId("canvas-element");
    firePointer(el, "pointerdown", { clientX: 0, clientY: 0, pointerId: 3 });
    firePointer(el, "pointermove", { clientX: 2000, clientY: 0, pointerId: 3 });
    firePointer(el, "pointerup", { clientX: 2000, clientY: 0, pointerId: 3 });
    expect(onChange).toHaveBeenCalledTimes(1);
    const geom = onChange.mock.calls[0][0];
    expect(geom.x).toBe(1080);
  });

  it("does not call onChange if pointer up without move", () => {
    const onChange = vi.fn();
    render(<CanvasOverlay element={baseEl} onChange={onChange} />);
    const el = screen.getByTestId("canvas-element");
    firePointer(el, "pointerdown", { clientX: 50, clientY: 50, pointerId: 4 });
    firePointer(el, "pointerup", { clientX: 50, clientY: 50, pointerId: 4 });
    expect(onChange).not.toHaveBeenCalled();
  });
});
