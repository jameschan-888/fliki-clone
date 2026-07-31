# rev24 阶段 D P1-B: alert manager + HMAC + throttle.
#
# 4 内置规则: render_queue_full / queue_depth_high / error_rate_high / user_high_failure.
# 触发后 POST 给 ALERT_WEBHOOK_URL 带 HMAC-SHA256 签名; throttle 5min 防 storm.
from __future__ import annotations

import hmac, hashlib, json, os, threading, time, urllib.request, urllib.error
from typing import Any

ALERT_WEBHOOK_URL = os.environ.get("FLIKI_ALERT_WEBHOOK_URL", "")
ALERT_WEBHOOK_SECRET = os.environ.get("FLIKI_ALERT_WEBHOOK_SECRET", "fliki-alert-dev-secret-CHANGE-IN-PROD")
ALERT_THROTTLE_SEC = int(os.environ.get("FLIKI_ALERT_THROTTLE_SEC", "300"))
ALERT_ERROR_RATE_THRESHOLD = float(os.environ.get("FLIKI_ALERT_ERROR_RATE_THRESHOLD", "0.05"))
ALERT_USER_FAILURE_THRESHOLD = float(os.environ.get("FLIKI_ALERT_USER_FAILURE_THRESHOLD", "0.20"))
ALERT_MAX_QUEUE_DEPTH = int(os.environ.get("FLIKI_ALERT_MAX_QUEUE_DEPTH", "50"))


class _AlertManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_fire = {}
        self._fired_count = {}
        self._webhook_log = []  # 最近 50 条 fire 记录 (test/debug)

    def _is_throttled(self, rule_name):
        last = self._last_fire.get(rule_name, 0)
        return (time.time() - last) < ALERT_THROTTLE_SEC

    def _mark_fired(self, rule_name):
        self._last_fire[rule_name] = time.time()
        self._fired_count[rule_name] = self._fired_count.get(rule_name, 0) + 1
        self._log_webhook(rule_name, "fired")

    def _log_webhook(self, rule_name, status):
        self._webhook_log.append({"rule": rule_name, "status": status, "ts": time.time()})
        if len(self._webhook_log) > 50:
            self._webhook_log.pop(0)

    def _sign(self, payload_bytes):
        return "sha256=" + hmac.new(
            ALERT_WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()

    def fire(self, rule_name, severity, message, metrics):
        with self._lock:
            if self._is_throttled(rule_name):
                return {"fired": False, "reason": "throttled", "rule": rule_name, "remaining_sec": int(ALERT_THROTTLE_SEC - (time.time() - self._last_fire.get(rule_name, 0)))}
            payload = {
                "rule": rule_name,
                "severity": severity,
                "message": message,
                "metrics": metrics,
                "timestamp": int(time.time()),
            }
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            sig = self._sign(body)
            if not ALERT_WEBHOOK_URL:
                self._mark_fired(rule_name)
                return {"fired": True, "delivered": False, "reason": "no_webhook_url", "rule": rule_name, "payload": payload, "signature": sig}
            try:
                req = urllib.request.Request(
                    ALERT_WEBHOOK_URL, data=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Alert-Signature": sig,
                        "X-Alert-Rule": rule_name,
                    },
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    self._mark_fired(rule_name)
                    return {"fired": True, "delivered": True, "http_status": r.status, "rule": rule_name, "payload": payload, "signature": sig}
            except urllib.error.HTTPError as e:
                return {"fired": False, "reason": "http_" + str(e.code), "rule": rule_name, "payload": payload}
            except Exception as e:
                return {"fired": False, "reason": "exception:" + str(e), "rule": rule_name, "payload": payload}

    def reset_throttle(self):
        with self._lock:
            self._last_fire.clear()
            self._fired_count.clear()
            self._webhook_log.clear()

    def stats(self):
        with self._lock:
            return {"fired_count": dict(self._fired_count), "last_fire": dict(self._last_fire), "webhook_log": list(self._webhook_log)}


MANAGER = _AlertManager()


def eval_rules(con):
    out = []
    # 1) render_queue_full
    try:
        from workers.render_queue import get_active_count, MAX_CONCURRENT, get_queue_stats
        active = get_active_count()
        stats = get_queue_stats()
        queued = int(stats.get("queued", 0) or 0) + int(stats.get("processing", 0) or 0)
        metrics = {"active": active, "max_concurrent": MAX_CONCURRENT, "queued": queued}
        if active >= MAX_CONCURRENT:
            r = MANAGER.fire("render_queue_full", "warning",
                              "render_queue active=" + str(active) + " >= MAX_CONCURRENT=" + str(MAX_CONCURRENT), metrics)
            out.append({"rule": "render_queue_full", "severity": "warning", "triggered": True, "result": r, "metrics": metrics})
        else:
            out.append({"rule": "render_queue_full", "severity": "warning", "triggered": False, "metrics": metrics})
        # 1b) queue_depth_high
        if queued >= ALERT_MAX_QUEUE_DEPTH:
            r = MANAGER.fire("queue_depth_high", "warning",
                              "render_queue depth=" + str(queued) + " >= threshold=" + str(ALERT_MAX_QUEUE_DEPTH), metrics)
            out.append({"rule": "queue_depth_high", "severity": "warning", "triggered": True, "result": r, "metrics": metrics})
        else:
            out.append({"rule": "queue_depth_high", "severity": "warning", "triggered": False, "metrics": metrics})
    except Exception as e:
        out.append({"rule": "render_queue_full", "error": "exception: " + str(e)})

    # 2) error_rate_high
    try:
        row = con.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed FROM render_jobs WHERE created_at >= datetime('now', '-1 day')"
        ).fetchone()
        total = int(row[0] or 0)
        failed = int(row[1] or 0)
        rate = (failed / total) if total > 0 else 0.0
        metrics = {"total": total, "failed": failed, "rate": round(rate, 4), "threshold": ALERT_ERROR_RATE_THRESHOLD, "window": "24h"}
        if total >= 10 and rate > ALERT_ERROR_RATE_THRESHOLD:
            r = MANAGER.fire("error_rate_high", "critical",
                              "render_jobs 24h error rate " + str(round(rate, 4)) + " > " + str(ALERT_ERROR_RATE_THRESHOLD), metrics)
            out.append({"rule": "error_rate_high", "severity": "critical", "triggered": True, "result": r, "metrics": metrics})
        else:
            out.append({"rule": "error_rate_high", "severity": "critical", "triggered": False, "metrics": metrics})
    except Exception as e:
        out.append({"rule": "error_rate_high", "error": "exception: " + str(e)})

    # 3) user_high_failure
    try:
        rows = con.execute(
            "SELECT user_id, COUNT(*) AS total, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed FROM render_jobs WHERE user_id IS NOT NULL AND created_at >= datetime('now', '-1 day') GROUP BY user_id HAVING total >= 5"
        ).fetchall()
        for user_id, total, failed in rows:
            total = int(total or 0)
            failed = int(failed or 0)
            rate = (failed / total) if total > 0 else 0.0
            metrics = {"user_id": str(user_id), "total": total, "failed": failed, "rate": round(rate, 4), "threshold": ALERT_USER_FAILURE_THRESHOLD, "window": "24h"}
            if rate > ALERT_USER_FAILURE_THRESHOLD:
                rule_name = "user_high_failure:" + str(user_id)
                r = MANAGER.fire(rule_name, "warning",
                                  "user " + str(user_id) + " 24h failure rate " + str(round(rate, 4)) + " > " + str(ALERT_USER_FAILURE_THRESHOLD), metrics)
                out.append({"rule": "user_high_failure", "severity": "warning", "triggered": True, "user_id": str(user_id), "result": r, "metrics": metrics})
    except Exception as e:
        out.append({"rule": "user_high_failure", "error": "exception: " + str(e)})

    return out


def get_rules_info():
    return [
        {"name": "render_queue_full", "severity": "warning", "description": "render_queue active slots >= MAX_CONCURRENT", "threshold": None},
        {"name": "queue_depth_high", "severity": "warning", "description": "render_queue total queued+processing >= threshold", "threshold": ALERT_MAX_QUEUE_DEPTH},
        {"name": "error_rate_high", "severity": "critical", "description": "render_jobs 24h error rate > threshold", "threshold": ALERT_ERROR_RATE_THRESHOLD},
        {"name": "user_high_failure", "severity": "warning", "description": "user 24h failure rate > threshold (per-user, jobs >= 5)", "threshold": ALERT_USER_FAILURE_THRESHOLD},
    ]
