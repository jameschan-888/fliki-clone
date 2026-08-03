"""C3 billing and credits foundation.

Payments remain provider-neutral: subscription changes are persisted as pending/local
state and never reported as a completed external charge.
"""
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from db.connection import get_db

PLANS = {
    "free": {"name": "Free", "monthly_credits": 2160, "price_monthly": 0, "price_yearly": 0},
    "standard": {"name": "Standard", "monthly_credits": 6000, "price_monthly": 28, "price_yearly": 23},
    "premium": {"name": "Premium", "monthly_credits": 18000, "price_monthly": 88, "price_yearly": 73},
    "enterprise": {"name": "Enterprise", "monthly_credits": None, "price_monthly": None, "price_yearly": None},
}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_billing_tables(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS subscriptions (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL UNIQUE,
      plan TEXT NOT NULL DEFAULT 'free',
      billing_cycle TEXT NOT NULL DEFAULT 'monthly',
      status TEXT NOT NULL DEFAULT 'active',
      provider TEXT NOT NULL DEFAULT 'local',
      provider_customer_id TEXT,
      provider_subscription_id TEXT,
      current_period_end TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS credit_balances (
      user_id TEXT PRIMARY KEY,
      balance INTEGER NOT NULL DEFAULT 0,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS credit_ledger (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      delta INTEGER NOT NULL,
      balance_after INTEGER NOT NULL,
      reason TEXT NOT NULL,
      reference_id TEXT,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_created ON credit_ledger(user_id, created_at DESC);
    """)
    users = con.execute("SELECT id FROM users").fetchall()
    for row in users:
        user_id = row[0]
        if not con.execute("SELECT 1 FROM subscriptions WHERE user_id=?", (user_id,)).fetchone():
            now = _now()
            con.execute("INSERT INTO subscriptions (id,user_id,plan,created_at,updated_at) VALUES (?,?,?,?,?)", (uuid.uuid4().hex, user_id, "free", now, now))
            con.execute("INSERT INTO credit_balances (user_id,balance,updated_at) VALUES (?,?,?)", (user_id, PLANS["free"]["monthly_credits"], now))
    con.commit()


class SubscribeBody(BaseModel):
    plan: str = Field(pattern="^(free|standard|premium|enterprise)$")
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|yearly)$")


def _uid(request):
    from auth_router import get_user_id_from_request
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN", "message": "需要登录"})
    return user_id


def _state(con, user_id):
    ensure_billing_tables(con)
    subscription = con.execute("SELECT id,user_id,plan,billing_cycle,status,provider,current_period_end FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()
    balance = con.execute("SELECT balance,updated_at FROM credit_balances WHERE user_id=?", (user_id,)).fetchone()
    ledger = con.execute("SELECT id,delta,balance_after,reason,reference_id,created_at FROM credit_ledger WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (user_id,)).fetchall()
    return {"subscription": dict(subscription) if subscription else None, "credits": {"balance": balance[0] if balance else 0, "updated_at": balance[1] if balance else None, "ledger": [dict(row) for row in ledger]}}


def create_router(get_db=get_db):
    router = APIRouter(prefix="/billing", tags=["billing"])

    @router.get("/plans")
    def plans():
        return {"plans": [{"id": plan_id, **details} for plan_id, details in PLANS.items()]}

    @router.get("/me")
    def billing_me(request: Request):
        with get_db() as con:
            return _state(con, _uid(request))

    @router.post("/subscribe")
    def subscribe(body: SubscribeBody, request: Request):
        user_id = _uid(request)
        now = _now()
        with get_db() as con:
            ensure_billing_tables(con)
            if body.plan == "enterprise":
                raise HTTPException(status_code=422, detail={"error_code": "CONTACT_SALES", "message": "Enterprise 请联系销售"})
            current = con.execute("SELECT plan FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()
            if not current:
                con.execute("INSERT INTO subscriptions (id,user_id,created_at,updated_at) VALUES (?,?,?,?,?)", (uuid.uuid4().hex,user_id,now,now))
            con.execute("UPDATE subscriptions SET plan=?, billing_cycle=?, status='active', updated_at=? WHERE user_id=?", (body.plan, body.billing_cycle, now, user_id))
            amount = PLANS[body.plan]["monthly_credits"]
            if amount is not None:
                previous = con.execute("SELECT balance FROM credit_balances WHERE user_id=?", (user_id,)).fetchone()
                before = previous[0] if previous else 0
                after = before + amount
                con.execute("INSERT OR REPLACE INTO credit_balances VALUES (?,?,?)", (user_id, after, now))
                con.execute("INSERT INTO credit_ledger VALUES (?,?,?,?,?,?)", (uuid.uuid4().hex,user_id,amount,after,"subscription_grant",body.plan,now))
            con.commit()
            state = _state(con, user_id)
        state["payment"] = {"status": "not_charged", "provider": "local", "message": "已保存本地订阅状态，未执行外部扣款"}
        return state

    return router
