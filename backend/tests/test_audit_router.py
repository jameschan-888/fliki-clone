import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AuditRouterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.con = sqlite3.connect(self.tmp.name)
        self.con.row_factory = sqlite3.Row
        self.con.execute("CREATE TABLE users (id TEXT PRIMARY KEY, role TEXT NOT NULL)")
        self.con.execute("INSERT INTO users VALUES ('admin-1', 'admin')")
        self.con.commit()

    def tearDown(self):
        self.con.close()
        os.unlink(self.tmp.name)

    def test_ensure_and_write_audit_log(self):
        from audit_router import ensure_audit_table, write_audit
        ensure_audit_table(self.con)
        write_audit(self.con, "admin-1", "draft.delete", "workflow_draft", "draft-1", {"reason": "user_request"})
        row = self.con.execute("SELECT actor_user_id, action, resource_type, resource_id, metadata_json FROM audit_logs").fetchone()
        self.assertEqual(row[0], "admin-1")
        self.assertEqual(row[1], "draft.delete")
        self.assertEqual(row[2], "workflow_draft")
        self.assertEqual(row[3], "draft-1")
        self.assertIn("user_request", row[4])

    def test_router_exposes_owner_and_admin_queries(self):
        from audit_router import create_router
        router = create_router(lambda: self.con)
        paths = {route.path for route in router.routes}
        self.assertIn("/audit-logs/me", paths)
        self.assertIn("/audit-logs", paths)


if __name__ == "__main__":
    unittest.main()
