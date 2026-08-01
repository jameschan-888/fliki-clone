"""rev35 阶段 2 P0.3: /api/alerts/* webhook endpoints.

P0 拆分: 把 main.py 的 _ALERT_AUTH_REQUIRED_MSG + _require_user_id + 3 个 inline 路由
(/api/alerts/rules, /api/alerts/eval, /api/alerts/reset-throttle) 抽到独立 router.
"""
from fastapi import APIRouter, HTTPException, Request

from db.connection import get_db

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

_ALERT_AUTH_REQUIRED_MSG = {"error_code": "AUTH_REQUIRED", "message": "missing or invalid token"}


def _require_user_id(request: Request) -> str:
    """rev24 阶段 D P1-B: helper to require authenticated user (admin or user)."""
    from auth_router import get_user_id_from_request as _g
    uid = _g(request)
    if not uid:
        raise HTTPException(status_code=401, detail=_ALERT_AUTH_REQUIRED_MSG)
    return uid


@router.get("/rules")
def list_alert_rules(request: Request):
    """rev24 阶段 D P1-B: list alert rules (auth required)."""
    _require_user_id(request)
    from alerts import get_rules_info, MANAGER as _ALERT_MANAGER
    return {"rules": get_rules_info(), "manager_stats": _ALERT_MANAGER.stats()}


@router.post("/eval")
def eval_alerts(request: Request):
    """rev24 阶段 D P1-B: evaluate all rules, fire webhook for triggered ones (auth required)."""
    _require_user_id(request)
    from alerts import eval_rules
    con = get_db()
    try:
        results = eval_rules(con)
        triggered = [r for r in results if r.get("triggered")]
        return {"evaluated": len(results), "triggered": len(triggered), "results": results}
    finally:
        con.close()


@router.post("/reset-throttle")
def reset_alert_throttle(request: Request):
    """rev24 阶段 D P1-B: reset alert throttle (auth required). For testing / manual recovery."""
    _require_user_id(request)
    from alerts import MANAGER as _ALERT_MANAGER
    _ALERT_MANAGER.reset_throttle()
    return {"reset": True, "stats": _ALERT_MANAGER.stats()}