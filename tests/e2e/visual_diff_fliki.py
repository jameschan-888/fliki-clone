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
        page.screenshot(path=str(out), full_page=False)
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
    total = img_a.size[0] * img_a.size[1]
    px = sum(1 for p in diff.getdata() if any(c > 8 for c in p))
    return round(px / total, 4)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-local", action="store_true", help="只抓 fliki.ai 不抓本地 dist")
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
                report["pages"].append(rec)

            browser.close()
    finally:
        if server:
            server.terminate()
            try: server.wait(timeout=3)
            except Exception: pass

    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    n = sum(1 for r in report["pages"] if r.get("fliki_ok"))
    print(f"\nfliki.ai 抓取 {n}/{len(report['pages'])} 页成功")
    print(f"report: {REPORT}")
    return 0  # informational, never gate

if __name__ == "__main__":
    sys.exit(main())
