import os
import sqlite3
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class BillingRouterTest(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, role TEXT)")
        self.con.execute("INSERT INTO users VALUES ('u1', 'one@test', 'user')")
        self.con.commit()

    def tearDown(self):
        self.con.close()

    def test_bootstrap_and_state(self):
        from billing_router import ensure_billing_tables, _state
        ensure_billing_tables(self.con)
        state = _state(self.con, "u1")
        self.assertEqual(state["subscription"]["plan"], "free")
        self.assertEqual(state["credits"]["balance"], 2160)

    def test_plans_contract(self):
        from billing_router import PLANS, create_router
        self.assertEqual(set(PLANS), {"free", "standard", "premium", "enterprise"})
        paths = {route.path for route in create_router(lambda: self.con).routes}
        self.assertIn("/billing/plans", paths)
        self.assertIn("/billing/me", paths)
        self.assertIn("/billing/subscribe", paths)

    def test_consume_is_idempotent_by_reference(self):
        from billing_router import ensure_billing_tables, consume_credits
        ensure_billing_tables(self.con)
        first = consume_credits(self.con, "u1", 10, "render", "req-1")
        second = consume_credits(self.con, "u1", 10, "render", "req-1")
        self.assertTrue(first["consumed"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["balance"], 2150)
if __name__ == "__main__":
    unittest.main()
