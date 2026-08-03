import os
import sqlite3
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class ShareRouterTest(unittest.TestCase):
    def test_router_contract_and_table(self):
        from share_router import create_router, ensure_share_table
        con = sqlite3.connect(":memory:")
        ensure_share_table(con)
        paths = {route.path for route in create_router(lambda: con).routes}
        self.assertIn("/workflow-drafts/{draft_id}/share", paths)
        self.assertIn("/share/{token}", paths)
        self.assertIn("/share/{token}/embed", paths)
        con.close()

if __name__ == "__main__":
    unittest.main()
