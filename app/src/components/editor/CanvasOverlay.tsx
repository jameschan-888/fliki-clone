// CanvasOverlay: 1280x720 画布内 element 像素级 drag-resize.
// pointerdown/move/up + setPointerCapture.
// drag 期间本地 draft state (高频), pointerup 时一次性 onChange commit store.
// end() 直接重算几何, 不依赖 stale draft 闭包.
import { useCallback, useRef, useState } from "react";

type DragKind = "move" | "nw" | "ne" | "sw" | "se";

type OverlayEl = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

type Props = {
  element: OverlayEl;
  scale?: number;
  onChange: (geom: { x: number; y: number; width: number; height: number }) => void;
};

const CANVAS_W = 1280;
const CANVAS_H = 720;

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

function computeGeom(
  kind: DragKind,
  s: OverlayEl,
  dx: number,
  dy: number,
): OverlayEl {
  let nx = s.x, ny = s.y, nw = s.width, nh = s.height;
  if (kind === "move") {
    nx = clamp(s.x + dx, 0, CANVAS_W - s.width);
    ny = clamp(s.y + dy, 0, CANVAS_H - s.height);
  } else if (kind === "se") {
    nw = clamp(s.width + dx, 20, CANVAS_W - s.x);
    nh = clamp(s.height + dy, 20, CANVAS_H - s.y);
  } else if (kind === "nw") {
    const newW = clamp(s.width - dx, 20, s.width + s.x);
    const newH = clamp(s.height - dy, 20, s.height + s.y);
    nx = s.x + (s.width - newW);
    ny = s.y + (s.height - newH);
    nw = newW;
    nh = newH;
  } else if (kind === "ne") {
    nw = clamp(s.width + dx, 20, CANVAS_W - s.x);
    const newH = clamp(s.height - dy, 20, s.height + s.y);
    ny = s.y + (s.height - newH);
    nh = newH;
  } else if (kind === "sw") {
    const newW = clamp(s.width - dx, 20, s.width + s.x);
    nx = s.x + (s.width - newW);
    nw = newW;
    nh = clamp(s.height + dy, 20, CANVAS_H - s.y);
  }
  return { id: s.id, x: nx, y: ny, width: nw, height: nh };
}

export function CanvasOverlay(props: Props) {
  const scale = props.scale ?? 0.25;
  const W = CANVAS_W * scale;
  const H = CANVAS_H * scale;
  const el = props.element;
  const [draft, setDraft] = useState<OverlayEl | null>(null);
  const dragRef = useRef<{
    kind: DragKind;
    startGeom: OverlayEl;
    startPointer: { x: number; y: number };
  } | null>(null);

  const view = draft ?? el;

  const begin = useCallback((kind: DragKind, e: React.PointerEvent) => {
    const target = e.currentTarget as HTMLElement;
    try { target.setPointerCapture(e.pointerId); } catch (_e) { /* jsdom 不实现 */ }
    dragRef.current = {
      kind,
      startGeom: { id: el.id, x: el.x, y: el.y, width: el.width, height: el.height },
      startPointer: { x: e.clientX, y: e.clientY },
    };
  }, [el.x, el.y, el.width, el.height]);

  const move = useCallback((e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    const dx = (e.clientX - drag.startPointer.x) / scale;
    const dy = (e.clientY - drag.startPointer.y) / scale;
    setDraft(computeGeom(drag.kind, drag.startGeom, dx, dy));
  }, [scale]);

  const end = useCallback((e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    const target = e.currentTarget as HTMLElement;
    try {
      if (target.hasPointerCapture && target.hasPointerCapture(e.pointerId)) {
        target.releasePointerCapture(e.pointerId);
      }
    } catch (_e) { /* 容错 */ }
    dragRef.current = null;
    const dx = (e.clientX - drag.startPointer.x) / scale;
    const dy = (e.clientY - drag.startPointer.y) / scale;
    setDraft(null);
    if (dx === 0 && dy === 0) return; // 无移动, 不 commit
    const finalGeom = computeGeom(drag.kind, drag.startGeom, dx, dy);
    props.onChange({ x: finalGeom.x, y: finalGeom.y, width: finalGeom.width, height: finalGeom.height });
  }, [scale, props]);

  return (
    <div
      className="canvas-overlay"
      data-testid="canvas-overlay"
      style={{
        width: W + "px",
        height: H + "px",
        position: "relative",
        background: "#0d1226",
        border: "1px solid #2d3756",
        borderRadius: 6,
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      <div
        data-testid="canvas-element"
        style={{
          position: "absolute",
          left: view.x * scale + "px",
          top: view.y * scale + "px",
          width: view.width * scale + "px",
          height: view.height * scale + "px",
          background: "rgba(25,181,197,0.18)",
          border: "1px dashed #19b5c5",
          cursor: "move",
          touchAction: "none",
        }}
        onPointerDown={(e) => begin("move", e)}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={end}
      >
        {(["nw", "ne", "sw", "se"] as DragKind[]).map((kind) => (
          <span
            key={kind}
            data-testid={"handle-" + kind}
            aria-label={"resize-" + kind}
            style={{
              position: "absolute",
              width: 10,
              height: 10,
              background: "#19b5c5",
              borderRadius: 5,
              border: "1px solid #0d1226",
              touchAction: "none",
              ...(kind === "nw" ? { top: -5, left: -5, cursor: "nwse-resize" } : {}),
              ...(kind === "ne" ? { top: -5, right: -5, cursor: "nesw-resize" } : {}),
              ...(kind === "sw" ? { bottom: -5, left: -5, cursor: "nesw-resize" } : {}),
              ...(kind === "se" ? { bottom: -5, right: -5, cursor: "nwse-resize" } : {}),
            }}
            onPointerDown={(e) => { e.stopPropagation(); begin(kind, e); }}
            onPointerMove={move}
            onPointerUp={end}
            onPointerCancel={end}
          />
        ))}
      </div>
      <small
        data-testid="canvas-readout"
        style={{
          position: "absolute",
          bottom: 4,
          right: 6,
          color: "#7c8bb5",
          fontSize: 10,
          fontFamily: "ui-monospace, monospace",
          background: "rgba(13,18,38,0.7)",
          padding: "0 4px",
          borderRadius: 3,
        }}
      >
        {Math.round(view.width)}x{Math.round(view.height)} @ ({Math.round(view.x)},{Math.round(view.y)})
      </small>
    </div>
  );
}

export default CanvasOverlay;
