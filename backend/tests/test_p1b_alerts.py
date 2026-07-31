"""rev24 阶段 D P1-B: 告警 webhook 测试.

覆盖:
  - 3 端点 (rules / eval / reset-throttle) 全部 401 匿名
  - rules 端点返回 4 默认规则
  - eval 评估 4 规则, 触发 result.fired 字段
  - HMAC-SHA256 签名 (X-Alert-Signature, sha256=...)
  - throttle 5min 同 rule 不重复 fire
  - reset-throttle 清空 throttle
  - payload 含 rule/severity/message/metrics/timestamp
"""
import hashlib, hmac, json, os, subprocess, sys, threading, time, unittest, urllib.request, urllib.error

BACKEND = "http://127.0.0.1:5181"
ALERT_SECRET = "fliki-alert-dev-secret-CHANGE-IN-PROD"  # 默认


def _register(email: str, password: str = "test12345") -> dict:
    body = json.dumps({"email": email, "password": password, "role": "user"}).encode()
    req = urllib.request.Request(BACKEND + "/auth/register", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _auth(headers: dict, token: str = None) -> dict:
    if token:
        headers = dict(headers)
        headers["Authorization"] = "Bearer " + token
    return headers


class P1BAlertsTests(unittest.TestCase):
    """rev24 阶段 D P1-B: 告警 webhook end-to-end."""

    @classmethod
    def setUpClass(cls):
        try:
            with urllib.request.urlopen(BACKEND + "/health", timeout=3) as r:
                if r.status != 200:
                    raise unittest.SkipTest("backend not 200")
        except Exception:
            raise unittest.SkipTest("backend unreachable")
        cls.token = _register("p1b-" + str(int(time.time())) + "@e.com")["token"]

    def _post(self, path: str, token: str = None):
        req = urllib.request.Request(BACKEND + path, method="POST", headers=_auth({}, token))
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))

    def _get(self, path: str, token: str = None):
        req = urllib.request.Request(BACKEND + path, headers=_auth({}, token))
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))

    def _post_raw(self, path: str, token: str = None):
        req = urllib.request.Request(BACKEND + path, method="POST", headers=_auth({}, token))
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def _get_raw(self, path: str, token: str = None):
        req = urllib.request.Request(BACKEND + path, headers=_auth({}, token))
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_alerts_rules_requires_auth(self):
        code, _ = self._get_raw("/api/alerts/rules")
        self.assertEqual(code, 401, "rules 端点必须 401 匿名")

    def test_alerts_eval_requires_auth(self):
        code, _ = self._post_raw("/api/alerts/eval")
        self.assertEqual(code, 401, "eval 端点必须 401 匿名")

    def test_alerts_reset_requires_auth(self):
        code, _ = self._post_raw("/api/alerts/reset-throttle")
        self.assertEqual(code, 401, "reset-throttle 端点必须 401 匿名")

    def test_list_rules_returns_4_default(self):
        data = self._get("/api/alerts/rules", self.token)
        self.assertIn("rules", data)
        names = [r["name"] for r in data["rules"]]
        for expected in ("render_queue_full", "queue_depth_high", "error_rate_high", "user_high_failure"):
            self.assertIn(expected, names, f"missing rule {expected}")
        # 每条 rule 必须有 severity + description
        for r in data["rules"]:
            self.assertIn("severity", r)
            self.assertIn("description", r)
        self.assertIn("manager_stats", data)

    def test_eval_evaluates_4_rules(self):
        # 先 reset 防 throttle 干扰
        self._post("/api/alerts/reset-throttle", self.token)
        data = self._post("/api/alerts/eval", self.token)
        self.assertIn("evaluated", data)
        self.assertIn("triggered", data)
        self.assertIn("results", data)
        # 基础 3 规则 (render_queue_full / queue_depth_high / error_rate_high) 必出现;
        # user_high_failure 按触发用户一用户一行, evaluated >= 3.
        self.assertGreaterEqual(data["evaluated"], 3, f"基础 3 规则必评估, got evaluated={data['evaluated']}")
        rule_names = {r.get("rule") for r in data["results"] if r.get("rule")}
        for expected in ("render_queue_full", "queue_depth_high", "error_rate_high"):
            self.assertIn(expected, rule_names, f"missing base rule {expected}")
        # user_high_failure 可能 0~N 行 (每个触发用户一行), 仅当有触发用户时才在 results 里
        # 验证每条 result 有 rule 字段
        for r in data["results"]:
            self.assertIn("rule", r)
    def test_eval_triggered_alert_payload(self):
        self._post("/api/alerts/reset-throttle", self.token)
        data = self._post("/api/alerts/eval", self.token)
        triggered = [r for r in data["results"] if r.get("triggered")]
        if not triggered:
            self.skipTest("no alerts triggered (DB 状态决定, 可能正常)")
        for r in triggered:
            self.assertIn("result", r)
            res = r["result"]
            self.assertIn("fired", res)
            self.assertTrue(res["fired"], f"triggered 必须 fired: {res}")
            self.assertIn("payload", res)
            p = res["payload"]
            self.assertIn("rule", p)
            self.assertIn("severity", p)
            self.assertIn("message", p)
            self.assertIn("metrics", p)
            self.assertIn("timestamp", p)
            self.assertIn("signature", res)
            self.assertTrue(res["signature"].startswith("sha256="), f"signature 格式错: {res["signature"]}")

    def test_hmac_signature_valid(self):
        """HMAC-SHA256 签名可被外部验证 (用 ALERT_SECRET 重算 == signature)."""
        self._post("/api/alerts/reset-throttle", self.token)
        data = self._post("/api/alerts/eval", self.token)
        triggered = [r for r in data["results"] if r.get("triggered") and r["result"].get("signature")]
        if not triggered:
            self.skipTest("no alerts triggered")
        for r in triggered:
            p = r["result"]["payload"]
            sig = r["result"]["signature"]
            # 重算: payload 必须以 json compact 序列化 (seps=(",", ":"))
            body = json.dumps(p, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            expected = "sha256=" + hmac.new(ALERT_SECRET.encode(), body, hashlib.sha256).hexdigest()
            self.assertEqual(sig, expected, f"HMAC mismatch: {sig} vs {expected}")

    def test_throttle_same_rule_5min(self):
        """同 rule 5min 内不重复 fire (throttle)."""
        self._post("/api/alerts/reset-throttle", self.token)
        data1 = self._post("/api/alerts/eval", self.token)
        data2 = self._post("/api/alerts/eval", self.token)
        # 找任意一条 fired 规则, 第二次必须 throttled
        triggered1 = [r for r in data1["results"] if r.get("triggered") and r["result"].get("fired")]
        if not triggered1:
            self.skipTest("no rules fired in first eval")
        rule_name = triggered1[0]["result"]["rule"]
        # 第二次 eval 同 rule 应 throttled
        for r in data2["results"]:
            if r.get("triggered") and r["result"].get("rule") == rule_name:
                self.assertFalse(r["result"]["fired"], f"throttle 失败: {rule_name} 第二次应 throttled")
                self.assertEqual(r["result"].get("reason"), "throttled")
                break
        else:
            # 第二次没检测到同 rule (可能其他 rule 触发), 至少要看到 throttle 行为
            # 验证 manager_stats 有 last_fire 时间戳
            rules = self._get("/api/alerts/rules", self.token)
            self.assertGreater(len(rules["manager_stats"]["last_fire"]), 0, "throttle 应记录 last_fire")

    def test_reset_throttle_clears(self):
        """reset-throttle 后同 rule 可重新 fire."""
        self._post("/api/alerts/reset-throttle", self.token)
        data1 = self._post("/api/alerts/eval", self.token)
        triggered1 = [r for r in data1["results"] if r.get("triggered") and r["result"].get("fired")]
        if not triggered1:
            self.skipTest("no rules fired")
        rule_name = triggered1[0]["result"]["rule"]
        # reset
        reset_data = self._post("/api/alerts/reset-throttle", self.token)
        self.assertTrue(reset_data["reset"])
        self.assertEqual(len(reset_data["stats"]["fired_count"]), 0)
        self.assertEqual(len(reset_data["stats"]["last_fire"]), 0)
        # 再 eval 同 rule 应重 fire
        data2 = self._post("/api/alerts/eval", self.token)
        for r in data2["results"]:
            if r.get("triggered") and r["result"].get("rule") == rule_name:
                self.assertTrue(r["result"]["fired"], f"reset 后应可重 fire")
                break

    def test_eval_includes_queue_depth_metrics(self):
        """eval 评估 render_queue_full / queue_depth_high 时 metrics 含 active/max_concurrent/queued."""
        self._post("/api/alerts/reset-throttle", self.token)
        data = self._post("/api/alerts/eval", self.token)
        queue_rules = [r for r in data["results"] if r["rule"] in ("render_queue_full", "queue_depth_high")]
        self.assertEqual(len(queue_rules), 2)
        for r in queue_rules:
            if "metrics" in r:
                m = r["metrics"]
                self.assertIn("active", m)
                self.assertIn("max_concurrent", m)
                self.assertIn("queued", m)


if __name__ == "__main__":
    unittest.main()