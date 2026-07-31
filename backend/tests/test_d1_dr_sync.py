"""rev24 阶段 D D1-2: db_backup.py 自动同步 DR 副本到 disaster_recovery/app.db."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
BACKUP_SCRIPT = REPO / "scripts" / "db_backup.py"
BACKEND_ROOT = REPO / "backend"


class D1DRSyncTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(BACKEND_ROOT))
        from config import DB_PATH, DATA_DIR
        self.src_db = Path(DB_PATH)
        self.data_dir = Path(DATA_DIR)
        self.dr_dir = self.data_dir / "disaster_recovery"
        self.dr_path = self.dr_dir / "app.db"
        self._orig_dr_mtime = self.dr_path.stat().st_mtime if self.dr_path.exists() else 0

    def test_dr_path_exists_after_backup(self):
        """run db_backup.py backup -> disaster_recovery/app.db 必须存在并被刷新."""
        r = subprocess.run(
            ["py", str(BACKUP_SCRIPT), "backup"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        self.assertEqual(r.returncode, 0, msg=f"backup failed: {r.stderr}")
        self.assertTrue(self.dr_path.exists(), "DR 副本 disaster_recovery/app.db 必须存在")
        # mtime 必须 >= 原 mtime (新版)
        new_mtime = self.dr_path.stat().st_mtime
        self.assertGreaterEqual(new_mtime, self._orig_dr_mtime,
            f"DR 副本未被刷新 (orig={self._orig_dr_mtime}, new={new_mtime})")

    def test_dr_path_same_size_as_source(self):
        """DR 副本大小应 ≈ 主 DB 大小 (允许 0 差异, 同源 copy)."""
        r = subprocess.run(
            ["py", str(BACKUP_SCRIPT), "backup"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        self.assertEqual(r.returncode, 0)
        self.assertTrue(self.dr_path.exists())
        src_size = self.src_db.stat().st_size
        dr_size = self.dr_path.stat().st_size
        # SQLite copy 可能 page 对齐, 允许 < 1% 差异
        self.assertLessEqual(abs(src_size - dr_size) / max(src_size, 1), 0.01)

    def test_dr_output_contains_dr_synced(self):
        """backup 输出 JSON 必须含 dr_synced_to 字段."""
        r = subprocess.run(
            ["py", str(BACKUP_SCRIPT), "backup"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        self.assertEqual(r.returncode, 0)
        import json
        # output may have leading lines; find JSON object
        out = r.stdout
        json_start = out.find("{")
        self.assertGreater(json_start, -1, f"no JSON in output: {out!r}")
        data = json.loads(out[json_start:])
        self.assertIn("dr_synced_to", data, f"backup output 缺 dr_synced_to: {data}")
        self.assertTrue(data["dr_synced_to"].endswith("disaster_recovery\\app.db") or
                        data["dr_synced_to"].endswith("disaster_recovery/app.db"),
                        f"unexpected dr path: {data['dr_synced_to']}")


if __name__ == "__main__":
    unittest.main()
