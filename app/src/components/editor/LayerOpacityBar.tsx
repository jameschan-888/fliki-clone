// LayerOpacityBar: Timeline layer track 内的 mini opacity 拖动条.
// 类似 CanvasOverlay, pointerdown/move/up + setPointerCapture + 实时 commit store.
// 60x8 横向 bar, fill 按 opacity%, 颜色来自 layer.kind.
import { useCallback, useRef, useState } from "react";

type Props = {
  layerId: string;
  opacity: number;        // 0-100
  fillColor: string;
  onChange: (opacity: number) => void;
};

export function LayerOpacityBar(props: Props) {
  const [draft, setDraft] = useState<number | null>(null);
  const dragRef = useRef<{ startX: number; startOpacity: number; width: number } | null>(null);

  const view = draft ?? props.opacity;

  const begin = useCallback((e: React.PointerEvent) => {
    const target = e.currentTarget as HTMLElement;
    try { target.setPointerCapture(e.pointerId); } catch (_e) {}
    const rect = target.getBoundingClientRect();
    dragRef.current = {
      startX: e.clientX,
      startOpacity: props.opacity,
      width: rect.width || 60,
    };
  }, [props.opacity]);

  const move = useCallback((e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    const dx = e.clientX - drag.startX;
    const delta = (dx / drag.width) * 100;
    const next = Math.max(0, Math.min(100, Math.round(drag.startOpacity + delta)));
    setDraft(next);
  }, []);

  const end = useCallback((e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    const target = e.currentTarget as HTMLElement;
    try {
      if (target.hasPointerCapture && target.hasPointerCapture(e.pointerId)) {
        target.releasePointerCapture(e.pointerId);
      }
    } catch (_e) {}
    dragRef.current = null;
    const dx = e.clientX - drag.startX;
    const delta = (dx / drag.width) * 100;
    const next = Math.max(0, Math.min(100, Math.round(drag.startOpacity + delta)));
    if (next !== props.opacity) {
      props.onChange(next);
    }
    setDraft(null);
  }, [props]);

  return (
    <div
      data-testid={"layer-opacity-bar-" + props.layerId}
      onPointerDown={begin}
      onPointerMove={move}
      onPointerUp={end}
      onPointerCancel={end}
      style={{
        position: "relative",
        width: 60,
        height: 8,
        background: "rgba(255,255,255,0.12)",
        borderRadius: 4,
        cursor: "ew-resize",
        touchAction: "none",
        marginRight: 6,
        flexShrink: 0,
      }}
    >
      <div
        data-testid={"layer-opacity-fill-" + props.layerId}
        style={{
          width: view + "%",
          height: "100%",
          background: props.fillColor,
          borderRadius: 4,
          transition: draft != null ? "none" : "width 0.15s",
        }}
      />
      <span
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 8,
          color: "#fff",
          fontFamily: "ui-monospace, monospace",
          textShadow: "0 1px 1px rgba(0,0,0,0.5)",
          pointerEvents: "none",
        }}
      >
        {view}%
      </span>
    </div>
  );
}

export default LayerOpacityBar;
