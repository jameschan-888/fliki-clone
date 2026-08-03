import sqlite3
import sys
import unittest
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__file__)))
class BrandKitRouterTest(unittest.TestCase):
    def test_router_contract(self):
        from brand_kit_router import create_router, ensure_brand_kit_table
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE workspace_members (workspace_id TEXT, user_id TEXT, role TEXT)")
        ensure_brand_kit_table(con)
        paths = {route.path for route in create_router(lambda: con).routes}
        self.assertIn("/workspaces/{workspace_id}/brand-kit", paths)
        con.close()
if __name__ == "__main__": unittest.main()
