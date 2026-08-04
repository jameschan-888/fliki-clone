#!/usr/bin/env python3
"""Enum backend FastAPI routers + endpoints for HANDOVER_NEXT.md.

rev38 R10.
"""
import argparse, json, re, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
BACKEND_ROUTERS = BACKEND / "routers"
MAIN = BACKEND / "main.py"
HANDOVER = ROOT / "HANDOVER_NEXT.md"

RE_PREFIX = re.compile(r"""prefix\s*=\s*["']([^"']+)["']""")
RE_ROUTE = re.compile(r"""@(?:router|app)\.(get|post|put|delete|patch)\(\s*["']([^"']*)["']""")
RE_INCLUDE = re.compile(r"""app\.include_router\(\s*(\w+)""")
RE_APIR = re.compile(r"""APIRouter\([^)]*\)""")

IGNORED_FILES = {"config", "errors", "file_security", "highlight_scorer", "pixelle_prompts", "rate_limit", "request_context", "env_check", "autoedit_pipeline", "avatar_segment_pipeline", "secure_middleware", "static_server", "wav2lip_prototype", "main"}

def _is_router_file(name):
    if not name.endswith(".py"): return False
    if name.startswith(("_", "test_")): return False
    base = name[:-3]
    if base in IGNORED_FILES: return False
    return True

def enum_one(path):
    try: src = path.read_text(encoding="utf-8")
    except Exception: return {"file": path.name, "prefixes": [], "endpoints": []}
    prefixes = set()
    endpoints = []
    for m in RE_APIR.finditer(src):
        for pp in RE_PREFIX.findall(m.group(0)):
            prefixes.add(pp)
    for m in RE_INCLUDE.finditer(src):
        depth, i = 1, m.end()
        while i < len(src) and depth > 0:
            if src[i] == "(": depth += 1
            elif src[i] == ")": depth -= 1
            i += 1
        for pp in RE_PREFIX.findall(src[m.end():i]):
            prefixes.add(pp)
    for m in RE_ROUTE.finditer(src):
        verb = m.group(1).upper()
        endpoints.append((verb, m.group(2)))
    label = path.name if path.parent == BACKEND else "routers/" + path.name
    return {"file": label, "prefixes": sorted(prefixes), "endpoints": endpoints}

def enum_all():
    out = []
    for d in (BACKEND, BACKEND_ROUTERS):
        if not d.exists(): continue
        for f in sorted(d.iterdir()):
            if _is_router_file(f.name):
                out.append(enum_one(f))
    return out

def to_markdown(rows):
    L = ["| File | prefix | 关键 endpoint (verb + path) |", "|---|---|---|"]
    for r in rows:
        if not r["endpoints"] and not r["prefixes"]: continue
        prefix = ",".join(r["prefixes"]) or "(none)"
        eps = [(v, p) for v, p in r["endpoints"] if p and p.strip()][:6]
        endpoints = ", ".join(v + " " + p for v, p in eps)
        L.append("| " + r["file"] + " | " + prefix + " | " + (endpoints or "-") + " |")
    return chr(10).join(L)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--update-handover", action="store_true")
    ap.add_argument("--check-routes", action="store_true")
    args = ap.parse_args()
    rows = enum_all()
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if args.md or not (args.update_handover or args.check_routes):
        print(to_markdown(rows))
        return 0
    if args.check_routes:
        main_src = MAIN.read_text(encoding="utf-8")
        imported = set(m.group(1) for m in RE_INCLUDE.finditer(main_src))
        missing = []
        for r in rows:
            base = r["file"].split("/")[-1].replace(".py", "")
            if r["endpoints"] and not any(base in i for i in imported):
                missing.append(r["file"])
        if missing:
            print("WARN: " + str(len(missing)) + " router file(s) 定义 endpoint 但 main.py 未 import:")
            for m in missing: print("  - " + m)
            return 1
        print("OK: " + str(len(rows)) + " router 文件 + main.py 全部覆盖")
        return 0
    if args.update_handover:
        if not HANDOVER.exists():
            print("HANDOVER_NEXT.md 不存在, --update-handover 退出"); return 2
        old = HANDOVER.read_text(encoding="utf-8")
        bom = chr(0xfeff) if old.startswith(chr(0xfeff)) else ""
        body = old[1:] if bom else old
        md = to_markdown(rows)
        today = date.today().isoformat()
        ep_count = sum(len(r["endpoints"]) for r in rows)
        rev_lines = [
            "## " + today + " rev38+ - Router Path Table (auto-generated)",
            "",
            str(len(rows)) + " routers / " + str(ep_count) + " endpoints",
            "",
            "运行 " + chr(96)*2 + "python scripts/enum_routers.py --md" + chr(96)*2 + " 重生成.",
            md,
            "",
        ]
        rev_header = chr(10).join(rev_lines) + chr(10)
        HANDOVER.write_text(bom + rev_header + body, encoding="utf-8")
        print("updated: " + str(HANDOVER) + " (table size=" + str(len(md)) + " chars)")
        return 0
    return 0

if __name__ == "__main__":
    sys.exit(main())