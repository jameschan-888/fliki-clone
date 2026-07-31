"""数据库备份/恢复 CLI. rev15.

用法:
  python scripts/db_backup.py backup [--out PATH]
  python scripts/db_backup.py restore --from PATH [--confirm]
  python scripts/db_backup.py list
  python scripts/db_backup.py verify --from PATH

默认 DB 来自 backend.config.DB_PATH; 备份默认路径 data/backups/db-YYYYMMDD-HHMMSS.sqlite3
"""
import argparse, os, shutil, sys, time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
from config import DB_PATH, DATA_DIR  # noqa: E402


def backup(out_path=None):
    src = Path(DB_PATH)
    if not src.exists():
        return {"ok": False, "error": f"DB not found: {src}"}
    if out_path is None:
        ts = time.strftime("%Y%m%d-%H%M%S")
        out = Path(DATA_DIR) / "backups" / f"db-{ts}.sqlite3"
    else:
        out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # SQLite 推荐 online backup API 而不是 cp, 但 sqlite3 已创建 safe_copy; 直接 copy 也能
    # 因为 backend 仅用 sqlite3 单进程, 关闭连接后再 copy 安全
    shutil.copy2(src, out)
    size = out.stat().st_size
    # rev24 阶段 D D1-2 收口: 同步一份到 disaster_recovery/ 目录, 让 DR 副本随 backup 自动续期
    dr_dir = Path(DATA_DIR) / "disaster_recovery"
    dr_dir.mkdir(parents=True, exist_ok=True)
    dr_path = dr_dir / "app.db"
    shutil.copy2(out, dr_path)
    return {"ok": True, "path": str(out), "size_bytes": size, "src": str(src), "dr_synced_to": str(dr_path), "dr_size_bytes": dr_path.stat().st_size}


def list_backups():
    bdir = Path(DATA_DIR) / "backups"
    if not bdir.exists():
        return {"ok": True, "backups": []}
    rows = []
    for f in sorted(bdir.glob("db-*.sqlite3"), reverse=True):
        st = f.stat()
        rows.append({"name": f.name, "path": str(f), "size_bytes": st.st_size, "mtime": int(st.st_mtime)})
    return {"ok": True, "backups": rows}


def verify(path):
    import sqlite3
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"backup not found: {p}"}
    try:
        conn = sqlite3.connect(str(p))
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type=\"table\"")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
        return {"ok": True, "tables": tables, "count": len(tables)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def restore(from_path, confirm=False):
    src = Path(from_path)
    if not src.exists():
        return {"ok": False, "error": f"backup not found: {src}"}
    if not confirm:
        return {"ok": False, "error": "refuse restore without --confirm; current DB will be backed up to data/backups/auto/"}
    # 当前 DB 自动备份
    cur = Path(DB_PATH)
    if cur.exists():
        autots = int(time.time())
        autodir = Path(DATA_DIR) / "backups" / "auto"
        autodir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cur, autodir / f"db-{autots}.sqlite3")
    shutil.copy2(src, cur)
    return {"ok": True, "restored_from": str(src), "current_db": str(cur)}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_b = sub.add_parser("backup")
    p_b.add_argument("--out", default=None)
    p_r = sub.add_parser("restore")
    p_r.add_argument("--from", dest="src", required=True)
    p_r.add_argument("--confirm", action="store_true")
    p_l = sub.add_parser("list")
    p_v = sub.add_parser("verify")
    p_v.add_argument("--from", dest="src", required=True)
    args = parser.parse_args()
    if args.cmd == "backup":
        result = backup(args.out)
    elif args.cmd == "restore":
        result = restore(args.src, args.confirm)
    elif args.cmd == "list":
        result = list_backups()
    elif args.cmd == "verify":
        result = verify(args.src)
    else:
        result = {"ok": False, "error": "unknown cmd"}
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 2)


if __name__ == "__main__":
    main()
