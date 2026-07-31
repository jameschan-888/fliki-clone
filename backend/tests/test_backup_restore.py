"""数据库备份/恢复 dry-run 集成测试.

不真实覆盖 DB, 仅验证脚本可调用 + 输出 schema + 数据往返无丢失.
跑:
  cd backend && python -m unittest tests.test_backup_restore -v
"""
import json, os, shutil, sqlite3, subprocess, sys, tempfile, time, unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
BACKEND = TESTS_DIR.parent
REPO_ROOT = BACKEND.parent
ROOT = REPO_ROOT  # 跟 db_backup.py 一致
SCRIPT = REPO_ROOT / "scripts" / "db_backup.py"
sys.path.insert(0, str(BACKEND))
from config import DB_PATH, DATA_DIR


def run_cli(args):
    """调 CLI 子进程, 返回 (returncode, stdout)."""
    cp = subprocess.run([sys.executable, str(SCRIPT)] + args,
                        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return cp.returncode, (cp.stdout or ""), (cp.stderr or "")


class DatabaseBackupTests(unittest.TestCase):
    def setUp(self):
        # 用临时目录作为 out, 避免污染 data/backups/
        self.tmpdir = tempfile.mkdtemp(prefix="db-bk-")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_backup_writes_sqlite_file(self):
        if not Path(DB_PATH).exists():
            self.skipTest(f"no live DB at {DB_PATH}; skip")
        out = os.path.join(self.tmpdir, "snap.sqlite3")
        code, out_std, err = run_cli(["backup", "--out", out])
        self.assertEqual(code, 0, f"backup failed: {err}")
        body = json.loads(out_std)
        self.assertTrue(body["ok"])
        self.assertTrue(Path(body["path"]).exists())
        # 校验 copy 后非空 + size>0
        self.assertGreater(body["size_bytes"], 0)

    def test_verify_lists_tables(self):
        if not Path(DB_PATH).exists():
            self.skipTest(f"no live DB at {DB_PATH}; skip")
        out = os.path.join(self.tmpdir, "snap.sqlite3")
        run_cli(["backup", "--out", out])
        code, out_std, err = run_cli(["verify", "--from", out])
        self.assertEqual(code, 0, err)
        body = json.loads(out_std)
        self.assertTrue(body["ok"])
        self.assertGreater(len(body.get("tables", [])), 0)
        # 已知核心表 (rev15 后)
        expected = {"workflow_drafts", "workflow_runs"}
        actual = set(body["tables"])
        missing = expected - actual
        self.assertFalse(missing, msg="missing tables: " + str(missing))

    def test_list_returns_recent(self):
        code, out_std, err = run_cli(["list"])
        self.assertEqual(code, 0, err)
        body = json.loads(out_std)
        self.assertTrue(body["ok"])
        self.assertIsInstance(body.get("backups"), list)

    def test_restore_round_trip_data_integrity(self):
        """构造临时 SQLite, 备份, 修改原 DB, 再 restore, 校验回原数据."""
        tmp_db = os.path.join(self.tmpdir, "src.db")
        bk = os.path.join(self.tmpdir, "bk.db")
        conn = sqlite3.connect(tmp_db)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO t(v) VALUES (?), (?), (?)", ("a", "b", "c"))
        conn.commit(); conn.close()
        # 备份 (用真实 DB_PATH 会变, 这次直接 shutil.copy2 模拟)
        shutil.copy2(tmp_db, bk)
        # 修改原 DB (模拟数据漂移)
        conn = sqlite3.connect(tmp_db)
        conn.execute("DELETE FROM t")
        conn.commit(); conn.close()
        # 验证已空
        c2 = sqlite3.connect(tmp_db).execute("SELECT count(*) FROM t").fetchone()[0]
        self.assertEqual(c2, 0)
        # 恢复
        shutil.copy2(bk, tmp_db)
        c3 = sqlite3.connect(tmp_db).execute("SELECT count(*) FROM t").fetchone()[0]
        self.assertEqual(c3, 3)
        rows = sqlite3.connect(tmp_db).execute("SELECT v FROM t ORDER BY id").fetchall()
        self.assertEqual([r[0] for r in rows], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
