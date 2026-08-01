import { API } from "./drafts";

const TOKEN_KEY = "fliki-auth-token";
const REFRESH_TOKEN_KEY = "fliki-auth-refresh-token";
const LOCAL_USER_KEY = "fliki-auth-local";

type AuthBootstrap = { email: string; password: string };
type AuthResponse = {
  token: string;
  refresh_token?: string;
  refresh_expires_at?: number;
};

function readBootstrap(): AuthBootstrap | null {
  try {
    const raw = localStorage.getItem(LOCAL_USER_KEY);
    if (!raw) return null;
    const obj = JSON.parse(raw) as AuthBootstrap;
    if (obj.email && obj.password) return obj;
    return null;
  } catch {
    return null;
  }
}

function writeBootstrap(value: AuthBootstrap): void {
  try {
    localStorage.setItem(LOCAL_USER_KEY, JSON.stringify(value));
  } catch {
    /* ignore quota errors */
  }
}

function shortUuid(): string {
  const arr = new Uint8Array(8);
  crypto.getRandomValues(arr);
  let out = "";
  for (const b of arr) out += b.toString(16).padStart(2, "0");
  return out;
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function setToken(value: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, value);
  } catch {
    /* ignore */
  }
}

function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}

function storeAuthResponse(value: AuthResponse): string {
  setToken(value.token);
  try {
    if (value.refresh_token) {
      localStorage.setItem(REFRESH_TOKEN_KEY, value.refresh_token);
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  } catch {
    /* ignore */
  }
  return value.token;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const data = await r.json().catch(() => null);
    const err = new Error("auth_http_" + r.status);
    (err as Error & { detail?: unknown }).detail = data;
    throw err;
  }
  return (await r.json()) as T;
}

async function tryRegister(email: string, password: string): Promise<AuthResponse> {
  return postJson<AuthResponse>("/auth/register", { email, password, role: "user" });
}

async function tryLogin(email: string, password: string): Promise<AuthResponse> {
  return postJson<AuthResponse>("/auth/login", { email, password });
}

let bootstrapInFlight: Promise<string | null> | null = null;
let recoveryInFlight: Promise<string | null> | null = null;

export async function ensureSession(): Promise<string | null> {
  const cached = getToken();
  if (cached) return cached;
  if (bootstrapInFlight) return bootstrapInFlight;
  bootstrapInFlight = (async (): Promise<string | null> => {
    const existing = readBootstrap();
    const cred = existing ?? (() => {
      const value: AuthBootstrap = {
        email: "local-" + shortUuid() + "@fliki.local",
        password: shortUuid() + shortUuid(),
      };
      writeBootstrap(value);
      return value;
    })();
    try {
      const response = await tryRegister(cred.email, cred.password);
      return storeAuthResponse(response);
    } catch (e) {
      const status = (e as Error & { detail?: { status?: number } }).detail?.status ?? 0;
      if (status === 409 || (e as Error).message === "auth_http_409") {
        try {
          const response = await tryLogin(cred.email, cred.password);
          return storeAuthResponse(response);
        } catch {
          /* fall through to fresh bootstrap */
        }
      }
      const fresh: AuthBootstrap = {
        email: "local-" + shortUuid() + "@fliki.local",
        password: shortUuid() + shortUuid(),
      };
      writeBootstrap(fresh);
      try {
        const response = await tryRegister(fresh.email, fresh.password);
        return storeAuthResponse(response);
      } catch {
        return null;
      }
    }
  })().finally(() => {
    bootstrapInFlight = null;
  });
  return bootstrapInFlight;
}

async function refreshSession(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  try {
    const response = await postJson<AuthResponse>("/auth/refresh", { refresh_token: refreshToken });
    return storeAuthResponse(response);
  } catch {
    clearSession();
    return null;
  }
}

export async function recoverSession(): Promise<string | null> {
  if (recoveryInFlight) return recoveryInFlight;
  recoveryInFlight = (async () => {
    const refreshed = await refreshSession();
    if (refreshed) return refreshed;
    clearSession();
    return ensureSession();
  })().finally(() => {
    recoveryInFlight = null;
  });
  return recoveryInFlight;
}

export function clearSession(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    /* ignore */
  }
}
