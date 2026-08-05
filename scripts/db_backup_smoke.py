"""P0#3: 灾备 smoke 自动化 (真删真恢复 + hash 校验).

与 db_backup_drill.py 的区别:
- drill: 备份 -> 验证 -> 复制到 temp -> smoke test, 不动生产 DB.
- smoke: 沙箱里 复制 -> 真删 -> 从 backup 恢复 -> sha256 校验, 验证恢复链路真能跑通.

不破坏生产 DB, 在 backend/data/smoke/ 沙箱里做. 失败时非零退出.

用法:
  python scripts/db_backup_smoke.py

退出码: 0 = smoke passed, 2 = smoke failed.
"""
import argparse, hashlib, json, shutil, sqlite3, sys, time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
from config import DB_PATH, DATA_DIR  # noqa: E402
from db_backup import backup  # noqa: E402

SMOKE_DIR = Path(DATA_DIR) / "smoke"
REQUIRED_TABLES = ("users", "render_jobs", "workflow_runs", "workflow_drafts")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _row_counts(path: Path) -> dict:
    conn = sqlite3.connect(str(path))
    try:
        out = {}
        for t in REQUIRED_TABLES:
            try:
                out[t] = conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
            except sqlite3.OperationalError:
                out[t] = -1
        return out
    finally:
        conn.close()


def run_smoke() -> dict:
    start = time.time()
    steps = []
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    sandbox_src = SMOKE_DIR / "sandbox.sqlite3"
    sandbox_restored = SMOKE_DIR / "sandbox-restored.sqlite3"
    backup_path = None
    prod_db = Path(DB_PATH)

    if not prod_db.exists():
        return {"smoke_status": "failed", "failed_step": "precheck", "error": "production DB missing: " + str(prod_db), "elapsed_total_sec": 0.0}

    # 1) 复制生产 DB 到沙箱
    s = {"name": "copy_to_sandbox"}
    try:
        shutil.copy2(prod_db, sandbox_src)
        original_sha = _sha256(sandbox_src)
        original_size = sandbox_src.stat().st_size
        original_counts = _row_counts(sandbox_src)
        s["ok"] = True
        s["sha256"] = original_sha
        s["size_bytes"] = original_size
        s["counts"] = original_counts
    except Exception as e:
        s["ok"] = False
        s["error"] = str(e)
    steps.append(s)
    if not s["ok"]:
        return {"smoke_status": "failed", "failed_step": "copy_to_sandbox", "steps": steps, "elapsed_total_sec": round(time.time() - start, 3)}

    # 2) 备份 (放 sandbox 目录)
    s2 = {"name": "backup"}
    try:
        b = backup(SMOKE_DIR / ("smoke-db-" + time.strftime("%Y%m%d-%H%M%S") + ".sqlite3"))
        if not b.get("ok"):
            s2["ok"] = False
            s2["error"] = b.get("error")
        else:
            backup_path = Path(b["path"])
            s2["ok"] = True
            s2["path"] = str(backup_path)
            s2["size_bytes"] = b.get("size_bytes")
    except Exception as e:
        s2["ok"] = False
        s2["error"] = str(e)
    steps.append(s2)
    if not s2["ok"]:
        return {"smoke_status": "failed", "failed_step": "backup", "steps": steps, "elapsed_total_sec": round(time.time() - start, 3)}

    # 3) 真删沙箱
    s3 = {"name": "delete_sandbox"}
    try:
        sandbox_src.unlink()
        s3["ok"] = not sandbox_src.exists()
        s3["existed"] = True
    except Exception as e:
        s3["ok"] = False
        s3["error"] = str(e)
    steps.append(s3)
    if not s3["ok"]:
        return {"smoke_status": "failed", "failed_step": "delete_sandbox", "steps": steps, "elapsed_total_sec": round(time.time() - start, 3)}

    # 4) 从 backup 恢复 (真恢复)
    s4 = {"name": "restore_from_backup"}
    try:
        shutil.copy2(backup_path, sandbox_restored)
        s4["ok"] = sandbox_restored.exists()
        s4["path"] = str(sandbox_restored)
        s4["size_bytes"] = sandbox_restored.stat().st_size
    except Exception as e:
        s4["ok"] = False
        s4["error"] = str(e)
    steps.append(s4)
    if not s4["ok"]:
        return {"smoke_status": "failed", "failed_step": "restore_from_backup", "steps": steps, "elapsed_total_sec": round(time.time() - start, 3)}

    # 5) hash 校验
    s5 = {"name": "hash_check"}
    try:
        restored_sha = _sha256(sandbox_restored)
        s5["ok"] = restored_sha == original_sha
        s5["original_sha256"] = original_sha
        s5["restored_sha256"] = restored_sha
        s5["match"] = s5["ok"]
    except Exception as e:
        s5["ok"] = False
        s5["error"] = str(e)
    steps.append(s5)
    if not s5["ok"]:
        return {"smoke_status": "failed", "failed_step": "hash_check", "steps": steps, "elapsed_total_sec": round(time.time() - start, 3)}

    # 6) 行数 smoke
    s6 = {"name": "row_count_check"}
    try:
        restored_counts = _row_counts(sandbox_restored)
        match = all(restored_counts.get(t) == original_counts.get(t) for t in REQUIRED_TABLES)
        s6["ok"] = match
        s6["original"] = original_counts
        s6["restored"] = restored_counts
    except Exception as e:
        s6["ok"] = False
        s6["error"] = str(e)
    steps.append(s6)
    if not s6["ok"]:
        return {"smoke_status": "failed", "failed_step": "row_count_check", "steps": steps, "elapsed_total_sec": round(time.time() - start, 3)}

    # 7) cleanup
    s7 = {"name": "cleanup"}
    try:
        if sandbox_restored.exists():
            sandbox_restored.unlink()
        if backup_path and backup_path.exists() and backup_path.parent == SMOKE_DIR:
            backup_path.unlink()
        s7["ok"] = True
    except Exception as e:
        s7["ok"] = False
        s7["error"] = str(e)
    steps.append(s7)

    elapsed = round(time.time() - start, 3)
    return {
        "smoke_status": "passed" if all(x["ok"] for x in steps) else "failed",
        "rto_sec": elapsed,
        "rpo_note": "smoke 用现网 DB 复制, RPO = 0 (验证恢复链路完整性)",
        "steps": steps,
        "elapsed_total_sec": elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description="DB smoke: 沙箱真删真恢复 + hash 校验")
    args = parser.parse_args()
    result = run_smoke()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["smoke_status"] == "passed" else 2)


if __name__ == "__main__":
    main()
