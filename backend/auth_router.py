"""Simple JWT auth router (rev18 stage C 项 #6).

Endpoints:
  POST /auth/register   -> { email, password, role }  -> { token, user }
  POST /auth/login      -> { email, password }         -> { token, user }
  GET  /auth/me         -> Bearer token               -> { user }
  GET  /auth/users      -> (admin only)               -> list of users

JWT_SECRET env (default 'fliki-dev-secret-CHANGE-IN-PROD').
Implements bcrypt-like password hashing via hashlib.pbkdf2_hmac (stdlib only).

Design: minimal but functional. Real production needs:
- bcrypt/argon2 instead of pbkdf2
- refresh token rotation
- rate limiting on /login
- email verification flow
"""
import sys
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET = os.environ.get("FLIKI_JWT_SECRET", "fliki-dev-secret-CHANGE-IN-PROD")
JWT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


# ===== P2-Hardening: production must override JWT_SECRET =====
_DEFAULT_JWT_SECRET = "fliki-dev-secret-CHANGE-IN-PROD"


def validate_jwt_secret(strict):
    """启动时校验 JWT_SECRET. strict=True 强制占位符 raise, dev 默认警告.

    在 main.py 启动时调用:
      validate_jwt_secret(strict=(os.getenv("FLIKI_ENV") == "prod"))
    """
    env_value = os.environ.get("FLIKI_JWT_SECRET", _DEFAULT_JWT_SECRET)
    is_default = env_value == _DEFAULT_JWT_SECRET
    if is_default:
        placeholder = _DEFAULT_JWT_SECRET
        msg = "[auth_router] FLIKI_JWT_SECRET is still placeholder: " + placeholder + ". Set strong random string before FLIKI_ENV=prod."
        if strict:
            raise RuntimeError(msg)
        print(msg, file=sys.stderr)
    elif len(env_value) < 16:
        msg = "[auth_router] FLIKI_JWT_SECRET length only " + str(len(env_value)) + ", recommend >= 32 chars."
        if strict:
            raise RuntimeError(msg)
        print(msg, file=sys.stderr)

PBKDF2_ITERS = 600_000  # rev24 阶段 D P0: OWASP 2023 推荐 (原 100k 偏弱)
PBKDF2_ITERS_LEGACY = 100_000  # 兼容老 hash 验证


# rev24 阶段 D P0: PBKDF2 升级到 600k (OWASP 2023 推荐, 原 100k 偏弱).
# 兼容旧 hash: 老 hash 没 'iter:' 前缀, 用 PBKDF2_ITERS_LEGACY=100k 验.
# login 成功且 hash 是老格式时, 自动 rehash 用新 iter 并写回 db.
def _hash_pw(password: str, salt: str | None = None, iters: int | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    use_iters = iters if iters is not None else PBKDF2_ITERS
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), use_iters)
    return salt, f"{use_iters}:{h.hex()}"


def _verify_pw(password: str, salt: str, expected: str) -> bool:
    if ":" in expected:
        iters_str, hash_hex = expected.split(":", 1)
        use_iters = int(iters_str)
    else:
        # 老 hash: 100k iter
        use_iters = PBKDF2_ITERS_LEGACY
        hash_hex = expected
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), use_iters)
    return hmac.compare_digest(h.hex(), hash_hex)


def _make_token(user_id: str, role: str) -> str:
    header = json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    payload = json.dumps({
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_TTL_SECONDS,
    }, separators=(",", ":")).encode()
    h64 = _b64u(header)
    p64 = _b64u(payload)
    sig = hmac.new(JWT_SECRET.encode(), f"{h64}.{p64}".encode(), hashlib.sha256).digest()
    sig64 = _b64u_bytes(sig)
    return f"{h64}.{p64}.{sig64}"


def _b64u(s: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(s).rstrip(b"=").decode("ascii")


def _b64u_bytes(s: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(s).rstrip(b"=").decode("ascii")


def _decode_token(token: str) -> dict | None:
    try:
        h64, p64, sig64 = token.split(".")
        import base64
        h = base64.urlsafe_b64decode(h64 + "==")
        p = base64.urlsafe_b64decode(p64 + "==")
        sig = base64.urlsafe_b64decode(sig64 + "==")
        expected = hmac.new(JWT_SECRET.encode(), f"{h64}.{p64}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(p)
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def get_user_id_from_request(request) -> str | None:
    # request may be None when called outside a FastAPI route (e.g. unit tests
    # that invoke the underlying function directly). Be defensive.
    if request is None:
        return None
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    payload = _decode_token(auth[7:])
    return payload.get("sub") if payload else None


class RegisterBody(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)
    role: str = Field(default="user", pattern="^(user|admin)$")


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(body: RegisterBody, request: Request):
    from main import get_db  # late import to avoid circular
    con = get_db()
    try:
        existing = con.execute("SELECT id FROM users WHERE email=?", (body.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail={"error_code": "EMAIL_EXISTS", "message": "邮箱已注册", "hint": "改用 /auth/login"})
        user_id = uuid.uuid4().hex
        salt, pw_hash = _hash_pw(body.password)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        con.execute(
            "INSERT INTO users (id, email, password_salt, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, body.email.lower().strip(), salt, pw_hash, body.role, now, now),
        )
        con.commit()
        token = _make_token(user_id, body.role)
        return {"token": token, "user": {"id": user_id, "email": body.email, "role": body.role}}
    finally:
        con.close()


@router.post("/login")
def login(body: LoginBody):
    from main import get_db
    con = get_db()
    try:
        row = con.execute("SELECT id, email, password_salt, password_hash, role FROM users WHERE email=?", (body.email.lower().strip(),)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail={"error_code": "INVALID_CREDENTIALS", "message": "邮箱或密码错误", "hint": "检查 email/password"})
        if not _verify_pw(body.password, row[2], row[3]):
            raise HTTPException(status_code=401, detail={"error_code": "INVALID_CREDENTIALS", "message": "邮箱或密码错误", "hint": "检查 email/password"})
        # rev24 阶段 D P0: 老 hash (100k iter, 无 'iter:' 前缀) 登录后自动 rehash 到 600k
        if ":" not in row[3]:
            _, new_hash = _hash_pw(body.password, row[2])  # 复用原 salt
            con.execute("UPDATE users SET password_hash=?, updated_at=? WHERE id=?",
                        (new_hash, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), row[0]))
            con.commit()
        token = _make_token(row[0], row[4])
        return {"token": token, "user": {"id": row[0], "email": row[1], "role": row[4]}}
    finally:
        con.close()


@router.get("/me")
def me(request: Request):
    uid = get_user_id_from_request(request)
    if not uid:
        raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN", "message": "missing/invalid token"})
    from main import get_db
    con = get_db()
    try:
        row = con.execute("SELECT id, email, role, created_at FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error_code": "USER_NOT_FOUND"})
        return {"user": {"id": row[0], "email": row[1], "role": row[2], "created_at": row[3]}}
    finally:
        con.close()


@router.get("/users")
def list_users(request: Request):
    uid = get_user_id_from_request(request)
    if not uid:
        raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN"})
    from main import get_db
    con = get_db()
    try:
        actor = con.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
        if not actor or actor[0] != "admin":
            raise HTTPException(status_code=403, detail={"error_code": "ADMIN_ONLY", "message": "需要 admin 权限"})
        rows = con.execute("SELECT id, email, role, created_at FROM users ORDER BY created_at DESC LIMIT 100").fetchall()
        return {"users": [{"id": r[0], "email": r[1], "role": r[2], "created_at": r[3]} for r in rows]}
    finally:
        con.close()


# DB schema (idempotent create on import)
def ensure_users_table():
    from main import get_db
    con = get_db()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        con.commit()
    finally:
        con.close()
