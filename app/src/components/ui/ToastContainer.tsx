import { useEffect } from "react";

export type ToastKind = "ok" | "warning" | "error" | "info";
export type ToastItem = { id: number; kind: ToastKind; text: string };

type Props = {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
  autoHideMs?: number;
};

function ToastView({ item, onDismiss, autoHideMs }: { item: ToastItem; onDismiss: (id: number) => void; autoHideMs: number }) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(item.id), autoHideMs);
    return () => clearTimeout(t);
  }, [item.id, autoHideMs, onDismiss]);
  return <div className={"toast toast-" + item.kind} onClick={() => onDismiss(item.id)}>{item.text}</div>;
}

export function ToastContainer({ toasts, onDismiss, autoHideMs = 5000 }: Props) {
  if (toasts.length === 0) return null;
  return (
    <div className="toastContainer" role="status" aria-live="polite">
      {toasts.map((t) => (
        <ToastView key={t.id} item={t} onDismiss={onDismiss} autoHideMs={autoHideMs} />
      ))}
    </div>
  );
}

// helper: 创建 ToastItem, 用单调递增 id 避免 React key 冲突
let _nextToastId = 1;
export function makeToast(kind: ToastKind, text: string): ToastItem {
  return { id: _nextToastId++, kind, text };
}
