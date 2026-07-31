import { useEffect, useState } from "react";
import { API } from "../../api/drafts";

type Quick = {
  ok: boolean;
  gpu_available: boolean;
  ffmpeg_available: boolean;
  pytorch_installed: boolean;
  disk_free_gb: number;
  capabilities: Record<string, boolean>;
  warnings: string[];
};

type Full = Quick & Record<string, unknown>;

type Props = {
  refreshSeconds?: number;
};

function badgeLevel(q: Quick | null): "ok" | "warn" | "down" {
  if (!q) return "down";
  if (!q.ffmpeg_available) return "down";
  if (q.warnings.length || !q.gpu_available || q.disk_free_gb < 5) return "warn";
  return "ok";
}

export function EnvCheckBadge({ refreshSeconds = 60 }: Props) {
  const [quick, setQuick] = useState<Quick | null>(null);
  const [open, setOpen] = useState(false);
  const [full, setFull] = useState<Full | null>(null);
  const [loadingFull, setLoadingFull] = useState(false);

  useEffect(() => {
    let stop = false;
    let inFlight = false;
    let lastFetch = 0;
    const cacheMs = Math.max(refreshSeconds * 1000, 60_000);
    async function tick(force = false) {
      if (inFlight) return;
      if (!force && Date.now() - lastFetch < cacheMs) return;
      inFlight = true;
      try {
        const r = await fetch(API + "/env-check/quick");
        if (!r.ok) throw new Error("env-check failed");
        const data = (await r.json()) as Quick;
        if (!stop) setQuick(data);
        lastFetch = Date.now();
      } catch {
        if (!stop) setQuick(null);
      } finally {
        inFlight = false;
      }
    }
    void tick(true);
    const id = window.setInterval(() => { void tick(); }, cacheMs);
    return () => { stop = true; window.clearInterval(id); };
  }, [refreshSeconds]);

  async function openModal() {
    setOpen(true);
    setLoadingFull(true);
    try {
      const r = await fetch(API + "/env-check");
      if (r.ok) setFull((await r.json()) as Full);
    } catch {
      // 保留 quick 数据即可
    } finally {
      setLoadingFull(false);
    }
  }
  function refreshNow() {
    setQuick(null);
    void fetch(API + "/env-check/quick").then(async (r) => {
      if (r.ok) setQuick((await r.json()) as Quick);
    }).catch(() => setQuick(null));
  }

  const level = badgeLevel(quick);
  const label = level === "ok" ? "环境就绪" : level === "warn" ? "环境有警告" : "环境异常";

  return (
    <>
      <button type="button" className={"envBadge " + level} onClick={openModal} title={quick?.warnings.join("\n") || ""}>
        <span className="dot" /> {label}
      </button>
      {open && (
        <div className="modalMask" onClick={() => setOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modalHeader">
              <h3>环境诊断</h3>
              <div>
                <button type="button" onClick={refreshNow}>↻ 重新检查</button>
                <button type="button" onClick={() => setOpen(false)}>✕</button>
              </div>
            </div>
            {!quick ? <p className="error">无法连接后端 /env-check</p> : (
              <>
                <ul className="envList">
                  <li><span>FFmpeg</span><strong className={quick.ffmpeg_available ? "ok" : "down"}>{quick.ffmpeg_available ? "✓ 可用" : "✗ 缺失"}</strong></li>
                  <li><span>GPU</span><strong className={quick.gpu_available ? "ok" : "warn"}>{quick.gpu_available ? "✓ 可用" : "⚠ 不可用（CPU 渲染）"}</strong></li>
                  <li><span>PyTorch</span><strong className={quick.pytorch_installed ? "ok" : "warn"}>{quick.pytorch_installed ? "✓ 已装" : "⚠ 未装"}</strong></li>
                  <li><span>磁盘剩余</span><strong className={quick.disk_free_gb >= 5 ? "ok" : "warn"}>{quick.disk_free_gb.toFixed(1)} GB</strong></li>
                </ul>
                {quick.warnings.length > 0 && (
                  <div className="warnBox">
                    <strong>警告</strong>
                    <ul>{quick.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
                  </div>
                )}
                <div className="modalFoot">
                  <strong>能力</strong>
                  {loadingFull ? <p>加载中…</p> : full ? (
                    <ul className="capList">
                      {Object.entries(full.capabilities as Record<string, boolean>).map(([k, v]) => (
                        <li key={k}><span>{k}</span><strong className={v ? "ok" : "warn"}>{v ? "✓" : "✗"}</strong></li>
                      ))}
                    </ul>
                  ) : <p>未加载详细能力</p>}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}