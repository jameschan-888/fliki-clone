"""Pixel diff smoke for Marketing pages.

默认模式: 拿当前构建的 dist 截图与 baselines/*.png 比较；超过阈值 (默认 0.5% 像素) 视为视觉退化。
`--update-baselines` 把当前截图写入 baselines/ 作为下一轮比较基准。

依赖: playwright (含 chromium), Pillow, Python http.server。dist 必须先 build (npm run build)。

调用:
    python tests/e2e/visual_diff.py                   # 比较模式
    python tests/e2e/visual_diff.py --update-baselines # 更新基线
    python tests/e2e/visual_diff.py --threshold 1.0    # 阈值放宽到 1%
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

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "app" / "dist"
BASELINE = Path(__file__).resolve().parent / "visual_baselines"
REPORT = Path(__file__).resolve().parent / "visual_diff_report.json"


def pick_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_server(dist: Path):
    port = pick_port()
    log_path = ROOT / "logs" / "visual_diff_server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "wb")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(dist),
        stdout=log_f,
        stderr=subprocess.STDOUT,
    )
    base_url = "http://127.0.0.1:" + str(port)
    for _ in range(40):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return proc, base_url, log_f
        except OSError:
            time.sleep(0.1)
    return proc, base_url, log_f


def stop_server(proc, log_f):
    try:
        proc.terminate()
        proc.wait(timeout=4)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    log_f.close()


PAGES = [
    {"name": "home",        "path": "/index.html",       "viewport": (1280, 800)},
    {"name": "features",    "path": "/features.html",   "viewport": (1280, 900)},
    {"name": "characters",  "path": "/characters.html", "viewport": (1280, 900)},
    {"name": "pricing",     "path": "/pricing.html",    "viewport": (1280, 900)},
    {"name": "use-cases",   "path": "/use-cases.html",  "viewport": (1280, 900)},
    {"name": "terms",       "path": "/terms.html",      "viewport": (1280, 900)},
    {"name": "privacy",     "path": "/privacy.html",    "viewport": (1280, 900)},
    {"name": "help",        "path": "/help.html",       "viewport": (1280, 900)},
    {"name": "about",       "path": "/about.html",      "viewport": (1280, 900)},
    {"name": "contact",     "path": "/contact.html",    "viewport": (1280, 900)},
]


def capture(p, base_url, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    browser = p.chromium.launch()
    try:
        for entry in PAGES:
            w, h = entry["viewport"]
            ctx = browser.new_context(viewport={"width": w, "height": h})
            page = ctx.new_page()
            page.goto(base_url + entry["path"], wait_until="networkidle", timeout=10_000)
            try:
                page.wait_for_selector(".catalogNav, nav, #root, footer", timeout=4000)
            except Exception:
                time.sleep(0.5)
            png_path = output_dir / (entry["name"] + ".png")
            page.screenshot(path=str(png_path), full_page=True)
            paths[entry["name"]] = {
                "path": entry["path"],
                "png": str(png_path),
                "size": png_path.stat().st_size,
            }
            ctx.close()
    finally:
        browser.close()
    return paths


def diff_pixels(a, b):
    if not a.exists() or not b.exists():
        return {"diff_pixels": -1, "ratio": -1.0, "missing": True}
    ia = Image.open(a).convert("RGB")
    ib = Image.open(b).convert("RGB")
    if ia.size != ib.size:
        ib = ib.resize(ia.size)
    diff = ImageChops.difference(ia, ib)
    bbox = diff.getbbox()
    if not bbox:
        return {"diff_pixels": 0, "ratio": 0.0, "size": ia.size}
    px = list(diff.getdata())
    nonzero = sum(1 for r, g, blu in px if r > 5 or g > 5 or blu > 5)
    total = len(px)
    return {"diff_pixels": nonzero, "ratio": round(nonzero / max(total, 1), 6), "size": list(ia.size)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.005, help="差异比例上限, 默认 0.5%")
    ap.add_argument("--update-baselines", action="store_true")
    args = ap.parse_args()

    if not DIST.exists():
        print("FAIL: app/dist not found, please run 'npm run build' first")
        sys.exit(2)

    BASELINE.mkdir(parents=True, exist_ok=True)
    print("starting http server on dist ...")
    proc, base_url, log_f = start_server(DIST)
    try:
        with sync_playwright() as p:
            current_dir = Path(__file__).resolve().parent / "visual_capture"
            try:
                paths = capture(p, base_url, current_dir)
            except Exception as e:
                print("capture failed: " + str(e)[:200])
                stop_server(proc, log_f)
                sys.exit(2)
            print("captured %d pages into %s" % (len(paths), current_dir))

            if args.update_baselines:
                for name, meta in paths.items():
                    dst = BASELINE / (name + ".png")
                    shutil.copy(meta["png"], dst)
                print("UPDATED %d baselines" % len(paths))
                return

            summary = []
            all_ok = True
            for entry in PAGES:
                cur = Path(paths[entry["name"]]["png"])
                base = BASELINE / (entry["name"] + ".png")
                if not base.exists():
                    summary.append({
                        "page": entry["name"],
                        "missing_baseline": True,
                        "ok": True,
                        "skip": True,
                    })
                    continue
                diff = diff_pixels(cur, base)
                ratio = diff["ratio"]
                ok = ratio >= 0 and ratio <= args.threshold
                if not ok:
                    all_ok = False
                summary.append({
                    "page": entry["name"],
                    "ratio": ratio,
                    "diff_pixels": diff.get("diff_pixels"),
                    "size": diff.get("size"),
                    "ok": ok,
                    "threshold": args.threshold,
                })

            REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            failed = [s["page"] for s in summary if not s.get("ok") and not s.get("skip")]
            print("\n=== summary (threshold %s%%) ===" % (args.threshold * 100))
            for s in summary:
                tag = "SKIP" if s.get("skip") else ("PASS" if s.get("ok") else "FAIL")
                print("  %-12s %-12s ratio=%.4f diff=%s" % (
                    tag,
                    s["page"],
                    s.get("ratio", -1),
                    s.get("diff_pixels", "n/a"),
                ))
            print("\nreport: %s" % REPORT)
            if failed:
                print("FAIL pages above threshold: %s" % ", ".join(failed))
                sys.exit(1)
            print("PASS")
    finally:
        stop_server(proc, log_f)


if __name__ == "__main__":
    main()
