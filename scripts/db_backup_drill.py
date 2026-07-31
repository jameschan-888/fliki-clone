"""rev24 阶段 D P1-C: 灾备演练脚本 (DR drill).

完整闭环: backup → verify → restore to temp DB → smoke test → cleanup.
输出 JSON 报告给运维 / CI / 监控使用.

用法:
  python scripts/db_backup_drill.py                  # 完整 drill
  python scripts/db_backup_drill.py --keep-backup    # drill 完成后保留 backup (默认清)
  python scripts/db_backup_drill.py --no-cleanup     # 不清 temp restore (调试用)

退出码: 0 = drill 成功, 2 = drill 失败 (某步骤异常).
"""
import argparse, json, os, shutil, sqlite3, sys, time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
from config import DB_PATH, DATA_DIR  # noqa: E402
from db_backup import backup, verify as _verify, list_backups  # noqa: E402

DRILL_PREFIX = "drill-"
DRILL_TMP_DIR = Path(DATA_DIR) / "backups" / "drill-tmp"


def _smoke_test_db(path: Path) -> dict:
    """打开 db, 跑 sanity check: 可连接 + 关键表存在 + 各表行数."""
    required_tables = ("users", "render_jobs", "workflow_runs", "workflow_drafts")
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            missing = [t for t in required_tables if t not in tables]
            if missing:
                return {"ok": False, "error": f"missing required tables: {missing}", "tables": tables}
            # 行数核对
            counts = {}
            for t in required_tables:
                counts[t] = conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
            return {"ok": True, "tables": tables, "counts": counts, "missing": []}
        finally:
            conn.close()
    except Exception as e:
        return {"ok": False, "error": str(e), "tables": [], "counts": {}, "missing": list(required_tables)}


def run_drill(keep_backup: bool = False, no_cleanup: bool = False) -> dict:
    """完整 DR drill. 返回结构化结果 dict."""
    start = time.time()
    steps = []
    drill_backup = None
    drill_restore = None
    DRILL_TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: backup
    step0 = {"name": "backup", "start": int(time.time())}
    try:
        ts = time.strftime("%Y%m%d-%H%M%S")
        out_path = Path(DATA_DIR) / "backups" / (DRILL_PREFIX + "db-" + ts + ".sqlite3")
        b = backup(out_path)
        if not b.get("ok"):
            step0["ok"] = False
            step0["error"] = b.get("error")
        else:
            step0["ok"] = True
            step0["path"] = b["path"]
            step0["size_bytes"] = b["size_bytes"]
            drill_backup = out_path
    except Exception as e:
        step0["ok"] = False
        step0["error"] = "exception: " + str(e)
    step0["elapsed_sec"] = round(time.time() - step0.get("start", time.time()), 3)
    steps.append(step0)
    if not step0["ok"]:
        return {"drill_status": "failed", "failed_step": "backup", "steps": steps, "elapsed_total_sec": round(time.time() - start, 3)}

    # Step 2: verify
    step1 = {"name": "verify", "start": int(time.time())}
    try:
        v = _verify(drill_backup)
        step1["ok"] = v.get("ok", False)
        step1["table_count"] = v.get("count", 0)
        step1["tables"] = v.get("tables", [])
        if not v.get("ok"):
            step1["error"] = v.get("error")
    except Exception as e:
        step1["ok"] = False
        step1["error"] = "exception: " + str(e)
    step1["elapsed_sec"] = round(time.time() - step1["start"], 3)
    steps.append(step1)
    if not step1["ok"]:
        return {"drill_status": "failed", "failed_step": "verify", "steps": steps, "elapsed_total_sec": round(time.time() - start, 3)}

    # Step 3: restore to temp (NOT touching production DB)
    step2 = {"name": "restore_to_temp", "start": int(time.time())}
    drill_restore = DRILL_TMP_DIR / "restore-test.sqlite3"
    try:
        shutil.copy2(drill_backup, drill_restore)
        step2["ok"] = True
        step2["path"] = str(drill_restore)
        step2["size_bytes"] = drill_restore.stat().st_size
    except Exception as e:
        step2["ok"] = False
        step2["error"] = "exception: " + str(e)
    step2["elapsed_sec"] = round(time.time() - step2["start"], 3)
    steps.append(step2)
    if not step2["ok"]:
        return {"drill_status": "failed", "failed_step": "restore_to_temp", "steps": steps, "elapsed_total_sec": round(time.time() - start, 3)}

    # Step 4: smoke test on the restored DB
    step3 = {"name": "smoke_test", "start": int(time.time())}
    try:
        s = _smoke_test_db(drill_restore)
        step3["ok"] = s.get("ok", False)
        step3["tables"] = s.get("tables", [])
        step3["counts"] = s.get("counts", {})
        if not s.get("ok"):
            step3["error"] = s.get("error")
    except Exception as e:
        step3["ok"] = False
        step3["error"] = "exception: " + str(e)
    step3["elapsed_sec"] = round(time.time() - step3["start"], 3)
    steps.append(step3)
    if not step3["ok"]:
        return {"drill_status": "failed", "failed_step": "smoke_test", "steps": steps, "elapsed_total_sec": round(time.time() - start, 3)}

    # Step 5: cleanup temp
    step4 = {"name": "cleanup", "start": int(time.time())}
    try:
        if not no_cleanup and drill_restore.exists():
            drill_restore.unlink()
        step4["ok"] = True
        step4["kept_drilling_backup"] = bool(keep_backup)
    except Exception as e:
        step4["ok"] = False
        step4["error"] = "exception: " + str(e)
    step4["elapsed_sec"] = round(time.time() - step4["start"], 3)
    steps.append(step4)

    # cleanup drill backup (按参数)
    if not keep_backup and drill_backup and drill_backup.exists():
        try:
            drill_backup.unlink()
        except Exception:
            pass

    # 计算 RTO (recovery time objective) = drill 全程
    elapsed_total = round(time.time() - start, 3)
    return {
        "drill_status": "passed" if all(s["ok"] for s in steps) else "failed",
        "rto_sec": elapsed_total,
        "rpo_note": "drill 用现网 DB, RPO = 0 (定期 backup 间隔)",
        "backup_size_bytes": drill_backup.stat().st_size if drill_backup and drill_backup.exists() else (step0.get("size_bytes", 0)),
        "verify_table_count": step1.get("table_count", 0),
        "restore_test_passed": step3.get("ok", False),
        "steps": steps,
        "elapsed_total_sec": elapsed_total,
    }


def main():
    parser = argparse.ArgumentParser(description="DR drill: backup → verify → restore → smoke test → cleanup")
    parser.add_argument("--keep-backup", action="store_true", help="保留 drill backup 文件 (默认清掉)")
    parser.add_argument("--no-cleanup", action="store_true", help="不删 temp restore (调试用)")
    args = parser.parse_args()
    result = run_drill(keep_backup=args.keep_backup, no_cleanup=args.no_cleanup)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["drill_status"] == "passed" else 2)


if __name__ == "__main__":
    main()
