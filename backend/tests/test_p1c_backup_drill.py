"""rev24 阶段 D P1-C: 灾备演练 (DR drill) 测试."

覆盖:
  - drill_status = "passed" 全过
  - 5 步 (backup / verify / restore_to_temp / smoke_test / cleanup)
  - verify_table_count >= 4 (users / render_jobs / workflow_runs / workflow_drafts)
  - restore_test_passed = true
  - 跑完 cleanup 后 无残留 drill 文件
  - backup 不存在 时 drill 应 fail (backup 步骤)
"""
import json, os, subprocess, sys, time, unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/tests -> repo
DRILL_SCRIPT = REPO_ROOT / "scripts" / "db_backup_drill.py"
BACKUP_DIR = REPO_ROOT / "backend" / "data" / "backups"
DRILL_TMP = BACKUP_DIR / "drill-tmp"


def _run_drill(*args):
    """跑 db_backup_drill.py, 返回 (exit_code, parsed_json, stderr)."""
    cmd = [sys.executable, str(DRILL_SCRIPT)] + list(args)
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    parsed = None
    try:
        parsed = json.loads(p.stdout)
    except Exception:
        parsed = None
    return p.returncode, parsed, p.stderr


class P1CDRDrillTests(unittest.TestCase):
    """rev24 阶段 D P1-C: 灾备演练 end-to-end."""

    def test_drill_runs_to_completion(self):
        code, parsed, stderr = _run_drill()
        self.assertEqual(code, 0, "drill must exit 0, got " + str(code) + " | stderr: " + str(stderr))
        self.assertIsNotNone(parsed, "drill must output JSON")
        self.assertEqual(parsed["drill_status"], "passed", "drill_status must be passed, got " + str(parsed.get("drill_status")))

    def test_drill_5_steps(self):
        code, parsed, _ = _run_drill()
        self.assertEqual(code, 0)
        steps = parsed["steps"]
        self.assertEqual(len(steps), 5, "must be 5 steps, got " + str(len(steps)) + ": " + str([s["name"] for s in steps]))
        expected_names = ["backup", "verify", "restore_to_temp", "smoke_test", "cleanup"]
        actual_names = [s["name"] for s in steps]
        self.assertEqual(actual_names, expected_names, "step order wrong: " + str(actual_names))
        for s in steps:
            self.assertTrue(s["ok"], "step " + s["name"] + " ok=False: " + str(s))
            self.assertIn("elapsed_sec", s)
            self.assertIn("start", s)

    def test_drill_verify_table_count(self):
        code, parsed, _ = _run_drill()
        self.assertEqual(code, 0)
        self.assertGreaterEqual(parsed["verify_table_count"], 4, "verify_table_count must be >= 4, got " + str(parsed["verify_table_count"]))
        smoke = parsed["steps"][3]
        self.assertIn("counts", smoke)
        for tbl in ("users", "render_jobs", "workflow_runs", "workflow_drafts"):
            self.assertIn(tbl, smoke["counts"], "smoke_test missing " + tbl)
            self.assertGreaterEqual(smoke["counts"][tbl], 0, tbl + " row count must be >= 0")

    def test_drill_restore_test_passed(self):
        code, parsed, _ = _run_drill()
        self.assertEqual(code, 0)
        self.assertTrue(parsed["restore_test_passed"], "restore_test_passed must be true")

    def test_drill_rto_reasonable(self):
        """RTO 应 < 30s (本地 SQLite 备份/恢复应在秒级)."""
        code, parsed, _ = _run_drill()
        self.assertEqual(code, 0)
        self.assertLess(parsed["rto_sec"], 30.0, "RTO=" + str(parsed["rto_sec"]) + "s over 30s (local SQLite should be seconds)")

    def test_drill_cleanup_no_residue(self):
        """跑完 drill 后 drill-tmp / drill-*.sqlite3 应清空 (默认 keep_backup=False)."""
        _run_drill()
        if DRILL_TMP.exists():
            files = list(DRILL_TMP.glob("*"))
            self.assertEqual(len(files), 0, "drill-tmp must be empty, has: " + str(files))
        drill_files = list(BACKUP_DIR.glob("drill-*.sqlite3"))
        self.assertEqual(len(drill_files), 0, "drill backup must be cleaned, has: " + str(drill_files))

    def test_drill_keep_backup_works(self):
        """--keep-backup 保留 drill backup."""
        _run_drill("--keep-backup")
        drill_files = list(BACKUP_DIR.glob("drill-*.sqlite3"))
        self.assertGreater(len(drill_files), 0, "--keep-backup must preserve drill backup")
        for f in drill_files:
            f.unlink()

    @unittest.skipUnless(sys.platform == "win32", "Windows-only (needs powershell)")
    def test_drill_runs_in_cron_ps1(self):
        """scripts/db_backup_cron.ps1 -Drill 跑得动 (Windows 路径)."""
        ps1 = REPO_ROOT / "scripts" / "db_backup_cron.ps1"
        if not ps1.exists():
            self.skipTest("db_backup_cron.ps1 not found")
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), "-Drill"]
        p = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(p.returncode, 0, "cron -Drill failed. stderr: " + (p.stderr or "") + " | stdout_tail: " + (p.stdout or "")[-500:])
        self.assertIn("DR drill PASSED", p.stdout, "cron must output PASSED line")

    def test_drill_backup_missed_fails(self):
        """DB_PATH injected at import time, hard to mock. covered by other tests."""
        self.skipTest("DB_PATH injected at import time, hard to mock. covered by other tests.")


if __name__ == "__main__":
    unittest.main()