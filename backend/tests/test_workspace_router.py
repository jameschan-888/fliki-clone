import os
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class WorkspaceRouterTest(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, role TEXT)")
        self.con.executemany("INSERT INTO users VALUES (?, ?, ?)", [("u1", "one@test", "user"), ("u2", "two@test", "user")])
        self.con.commit()

    def tearDown(self):
        self.con.close()

    def test_bootstrap_creates_one_workspace_per_user(self):
        from workspace_router import ensure_workspace_tables
        ensure_workspace_tables(self.con)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0], 2)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM workspace_members").fetchone()[0], 2)
        self.assertEqual(self.con.execute("SELECT role FROM workspace_members WHERE user_id='u1'").fetchone()[0], "owner")

    def test_router_has_workspace_contract(self):
        from workspace_router import create_router
        router = create_router(lambda: self.con)
        paths = {route.path for route in router.routes}
        self.assertIn("/workspaces", paths)
        self.assertIn("/workspaces/{workspace_id}/members", paths)
        self.assertIn("/workspaces/{workspace_id}/members", paths)

if __name__ == "__main__":
    unittest.main()
