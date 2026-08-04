"""fliki.ai ↔ project dist 1:1 pixel comparison.

抓 fliki.ai 公共页 (/, /features, /pricing, /ai-video-generator, /text-to-speech)
存到 fliki_research/screenshots/. 同时启动本地 http server 跑 dist, 抓对应营销页.
两套截图做 side-by-side diff, 写到 fliki_research/diff_vs_project.json.

非 gate (informational): 拿不到 fliki.ai 或网络不通就跳过, exit 0.
Cookie banner 用 page.context.add_cookies 拒非必要 cookie 绕过.
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
# Lazy imports: numpy/skimage 缺包不破 (informational, never gate, 但 user setup 不炸)
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
try:
    from skimage.metrics import structural_similarity
    _HAS_SSIM = True
except ImportError:
    _HAS_SSIM = False

ROOT = Path(__file__).resolve().parents[2]  # tests/e2e -> tests -> project root
DIST = ROOT / "app" / "dist"
SCREENSHOTS = ROOT / "fliki_research" / "screenshots"
REPORT = ROOT / "fliki_research" / "diff_vs_project.json"

PAGES = [
    ("home",                "/",                   "/"),
    ("features",            "/features",           "/features"),
    ("pricing",             "/pricing",            "/pricing"),
    ("ai-video-generator",  "/ai-video-generator", "/features"),
    ("text-to-speech",      "/text-to-speech",     "/characters"),
]

FLIKI_BASE = "https://fliki.ai"

def pick_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p

def start_dist_server(port: int) -> subprocess.Popen:
    if not (DIST / "index.html").exists():
        print(f"[local] dist missing at {DIST} -- run 'npm run build' first", file=sys.stderr)
        return None
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--directory", str(DIST)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # wait ready
    for _ in range(40):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return proc
            break  # unreachable branch, kept for clarity
        except OSError:
            time.sleep(0.25)
    # final attempt (silent if succeeded mid-loop)
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return proc
    except OSError:
        proc.terminate()
        return None

def shot(page, url: str, out: Path, label: str) -> bool:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(out), full_page=True)
        print(f"  [{label}] -> {out.name} ({out.stat().st_size} bytes)")
        return True
    except (PWTimeout, Exception) as e:
        print(f"  [{label}] FAILED: {type(e).__name__}: {str(e)[:100]}")
        return False

def diff_ratio(a: Path, b: Path) -> float:
    if not a.exists() or not b.exists():
        return -1.0
    img_a, img_b = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if img_a.size != img_b.size:
        # resize b to a for ratio only
        img_b = img_b.resize(img_a.size)
    diff = ImageChops.difference(img_a, img_b)
    bbox = diff.getbbox()
    if not bbox:
        return 0.0
    # pixel-level ratio
    # N47 numpy mask path; lazy fallback if numpy 缺包
    if _HAS_NUMPY:
        arr = np.array(diff)
        total = arr.shape[0] * arr.shape[1]
        px = int((np.any(arr > 8, axis=2)).sum())
    else:
        total = img_a.size[0] * img_a.size[1]
        px = sum(1 for p in diff.getdata() if any(c > 8 for c in p))
    return round(px / total, 4)

def diff_metrics(a: Path, b: Path) -> dict:
    # N41/N42 pitfall: thr=8 字体噪声天花板. 返 pixel_thr8/32 + ssim.
    if not a.exists() or not b.exists():
        return { "ok": False }
    img_a = Image.open(a).convert("RGB")
    img_b = Image.open(b).convert("RGB")
    same_size = img_a.size == img_b.size
    if not same_size:
        img_b = img_b.resize(img_a.size)
    diff = ImageChops.difference(img_a, img_b)
    bbox = diff.getbbox()
    if not bbox:
        return { "ok": True, "same_size": same_size,
                "pixel_thr8": 0.0, "pixel_thr32": 0.0, "ssim": 1.0 }
    if _HAS_NUMPY:
        arr = np.array(diff)
        px8  = float((np.any(arr > 8,  axis=2)).mean())
        px32 = float((np.any(arr > 32, axis=2)).mean())
    else:
        total = img_a.size[0] * img_a.size[1]
        px8  = sum(1 for p in diff.getdata() if any(c > 8  for c in p)) / total
        px32 = sum(1 for p in diff.getdata() if any(c > 32 for c in p)) / total
    ssim_v = None
    if _HAS_SSIM and _HAS_NUMPY:
        try:
            arr_a = np.array(img_a)
            arr_b = np.array(img_b)
            if arr_a.shape == arr_b.shape:
                ssim_v = float(structural_similarity(arr_a, arr_b, channel_axis=2))
        except Exception:
            ssim_v = None
    return { "ok": True, "same_size": same_size,
            "pixel_thr8": round(px8, 4),
            "pixel_thr32": round(px32, 4),
            "ssim": round(ssim_v, 4) if ssim_v is not None else None }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-local", action="store_true", help="只抓 fliki.ai 不抓本地 dist")
    ap.add_argument("--sync-baseline-threshold", type=float, default=0.0, help="如果 fliki vs project diff_ratio < 此阈值, 自动把 project 截图写入 visual_baselines/project_<id>.png")
    ap.add_argument("--pages", nargs="*", help="只跑指定页 id (subset of " + ",".join(p[0] for p in PAGES) + ")")
    args = ap.parse_args()

    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    pages = [p for p in PAGES if not args.pages or p[0] in args.pages]

    report: Dict = {"captured_at": time.strftime("%Y-%m-%d %H:%M:%S"), "pages": []}

    # local server
    server = None
    if not args.skip_local:
        port = pick_port()
        server = start_dist_server(port)
        if server:
            print(f"[local] dist server up on :{port}")
        else:
            print("[local] dist server FAILED to start", file=sys.stderr)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            # reject non-essential cookies (best-effort)
            try:
                ctx.add_cookies([{"name": "OptanonAlertBoxClosed", "value": time.strftime("%Y-%m-%dT%H:%M:%S"), "url": FLIKI_BASE}])
            except Exception:
                pass

            fliki_page = ctx.new_page()
            local_page = ctx.new_page() if server else None

            for pid, fliki_path, local_path in pages:
                print(f"--- {pid} ---")
                rec = {"id": pid, "fliki_url": FLIKI_BASE + fliki_path, "local_url": f"http://127.0.0.1:{port}{local_path}" if server else None}
                # fliki
                fliki_out = SCREENSHOTS / f"fliki_{pid}.png"
                rec["fliki_ok"] = shot(fliki_page, FLIKI_BASE + fliki_path, fliki_out, f"fliki:{pid}")
                # local
                if local_page and server:
                    local_out = SCREENSHOTS / f"project_{pid}.png"
                    rec["local_ok"] = shot(local_page, f"http://127.0.0.1:{port}{local_path}", local_out, f"local:{pid}")
                    if rec["local_ok"]:
                        rec["diff_ratio"] = diff_ratio(fliki_out, local_out)
                        rec["diff"] = diff_metrics(fliki_out, local_out)
                report["pages"].append(rec)

            browser.close()
    finally:
        if server:
            server.terminate()
            try: server.wait(timeout=3)
            except Exception: pass
        if args.sync_baseline_threshold > 0:
            sync_count = 0
            BASELINE_DIR = ROOT / "tests" / "e2e" / "visual_baselines"
            BASELINE_DIR.mkdir(parents=True, exist_ok=True)
            for rec in report["pages"]:
                if rec.get("local_ok") and 0 <= rec.get("diff_ratio", 1) <= args.sync_baseline_threshold:
                    src = SCREENSHOTS / f"project_{rec['id']}.png"
                    if src.exists():
                        dst = BASELINE_DIR / f"project_{rec['id']}.png"
                        import shutil
                        shutil.copy2(src, dst)
                        print(f"  [sync] {rec['id']} diff={rec['diff_ratio']:.4f} -> {dst.name}")
                        sync_count += 1
            if sync_count:
                print(f"sync: {sync_count} page(s) -> {BASELINE_DIR}")

        REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    n = sum(1 for r in report["pages"] if r.get("fliki_ok"))
    print(f"\nfliki.ai 抓取 {n}/{len(report['pages'])} 页成功")
    print(f"report: {REPORT}")
    return 0  # informational, never gate

if __name__ == "__main__":
    sys.exit(main())
