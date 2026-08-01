import { describe, it, expect, beforeEach, vi } from "vitest";

// rev31: 自动注册 bootstrap + 401 重试回归保护

const TOKEN_KEY = "fliki-auth-token";
const REFRESH_TOKEN_KEY = "fliki-auth-refresh-token";
const LOCAL_USER_KEY = "fliki-auth-local";

function makeFetch(handler: (url: string, init?: RequestInit) => Response): typeof fetch {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : (input as URL).toString();
    return handler(url, init);
  });
  return fn as unknown as typeof fetch;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("ensureSession (rev31)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("registers a fresh local user when no token cached", async () => {
    const f = makeFetch((url) => {
      if (url.endsWith("/auth/register")) {
        return json({ token: "tok-A", refresh_token: "refresh-A", user: { id: "u-A" } });
      }
      return json({}, 404);
    });
    globalThis.fetch = f;
    const auth = await import("./auth");
    const tok = await auth.ensureSession();
    expect(tok).toBe("tok-A");
    expect(localStorage.getItem(TOKEN_KEY)).toBe("tok-A");
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-A");
    const cached = localStorage.getItem(LOCAL_USER_KEY);
    expect(cached).not.toBeNull();
    const parsed = JSON.parse(cached!);
    expect(parsed.email).toMatch(/^local-[a-f0-9]+@fliki\.local$/);
    expect(parsed.password.length).toBeGreaterThanOrEqual(16);
  });

  it("logs in when register returns 409", async () => {
    localStorage.setItem(LOCAL_USER_KEY, JSON.stringify({ email: "local-x@fliki.local", password: "secret-pw" }));
    const f = makeFetch((url) => {
      if (url.endsWith("/auth/register")) return json({ detail: { error_code: "EMAIL_EXISTS" } }, 409);
      if (url.endsWith("/auth/login")) return json({ token: "tok-login" });
      return json({}, 404);
    });
    globalThis.fetch = f;
    const auth = await import("./auth");
    const tok = await auth.ensureSession();
    expect(tok).toBe("tok-login");
    expect(localStorage.getItem(TOKEN_KEY)).toBe("tok-login");
  });

  it("returns cached token without calling fetch", async () => {
    localStorage.setItem(TOKEN_KEY, "tok-cached");
    const f = vi.fn();
    globalThis.fetch = f as unknown as typeof fetch;
    const auth = await import("./auth");
    const tok = await auth.ensureSession();
    expect(tok).toBe("tok-cached");
    expect(f).not.toHaveBeenCalled();
  });
});

describe("drafts.request auto Bearer + 401 retry (rev31)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("injects Authorization header from cached token", async () => {
    localStorage.setItem(TOKEN_KEY, "tok-bearer");
    let captured: Record<string, string> | undefined;
    const f = makeFetch((url, init) => {
      if (url.endsWith("/workflow-drafts/draft-1")) {
        captured = init?.headers as Record<string, string>;
        return json({ id: "draft-1" });
      }
      return json({}, 404);
    });
    globalThis.fetch = f;
    const drafts = await import("./drafts");
    const out = await drafts.getDraft("draft-1");
    expect(out.id).toBe("draft-1");
    expect(captured?.["Authorization"]).toBe("Bearer tok-bearer");
  });

  it("on 401 calls ensureSession and retries once with new token", async () => {
    const calls: Array<{ url: string; auth?: string }> = [];
    const f = makeFetch((url, init) => {
      const auth = (init?.headers as Record<string, string> | undefined)?.["Authorization"];
      calls.push({ url, auth });
      if (url.endsWith("/workflow-drafts/d1") && !auth) {
        return json({ detail: { error_code: "MISSING_TOKEN" } }, 401);
      }
      if (url.endsWith("/auth/register")) return json({ token: "tok-new" });
      if (url.endsWith("/workflow-drafts/d1")) return json({ id: "draft-1" });
      return json({}, 404);
    });
    globalThis.fetch = f;
    const drafts = await import("./drafts");
    const out = await drafts.getDraft("d1");
    expect(out.id).toBe("draft-1");
    const draftCalls = calls.filter((c) => c.url.endsWith("/workflow-drafts/d1"));
    expect(draftCalls.length).toBe(2);
    expect(draftCalls[0].auth).toBeUndefined();
    expect(draftCalls[1].auth).toBe("Bearer tok-new");
    expect(localStorage.getItem(TOKEN_KEY)).toBe("tok-new");
  });

  it("stops after one retry (no infinite loop)", async () => {
    let fetchCount = 0;
    const f = makeFetch((url) => {
      fetchCount += 1;
      if (url.endsWith("/auth/register")) return json({ token: "tok-loop" });
      return json({ detail: "still 401" }, 401);
    });
    globalThis.fetch = f;
    const drafts = await import("./drafts");
    await expect(drafts.getDraft("loop")).rejects.toMatchObject({ status: 401 });
    // getDraft 401 -> ensureSession register 1 次 -> retry getDraft 401 (no more retries)
    // 总调用次数应受限: workflow-drafts 2 + register 1 = 3
    expect(fetchCount).toBeLessThanOrEqual(4);
  });

  it("rotates a cached refresh token before retrying an expired access token", async () => {
    localStorage.setItem(TOKEN_KEY, "tok-expired");
    localStorage.setItem(REFRESH_TOKEN_KEY, "refresh-old");
    const calls: Array<{ url: string; auth?: string; body?: string }> = [];
    const f = makeFetch((url, init) => {
      const auth = (init?.headers as Record<string, string> | undefined)?.["Authorization"];
      calls.push({ url, auth, body: typeof init?.body === "string" ? init.body : undefined });
      if (url.endsWith("/auth/refresh")) {
        return json({ token: "tok-fresh", refresh_token: "refresh-new" });
      }
      if (url.endsWith("/workflow-drafts/expired") && auth === "Bearer tok-fresh") {
        return json({ id: "draft-fresh" });
      }
      if (url.endsWith("/workflow-drafts/expired")) {
        return json({ detail: { error_code: "TOKEN_EXPIRED" } }, 401);
      }
      return json({}, 404);
    });
    globalThis.fetch = f;

    const drafts = await import("./drafts");
    const out = await drafts.getDraft("expired");

    expect(out.id).toBe("draft-fresh");
    const refreshCalls = calls.filter((call) => call.url.endsWith("/auth/refresh"));
    expect(refreshCalls).toHaveLength(1);
    expect(JSON.parse(refreshCalls[0].body ?? "{}")).toEqual({ refresh_token: "refresh-old" });
    expect(localStorage.getItem(TOKEN_KEY)).toBe("tok-fresh");
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-new");
  });

  it("shares one refresh rotation across concurrent 401 responses", async () => {
    localStorage.setItem(TOKEN_KEY, "tok-expired");
    localStorage.setItem(REFRESH_TOKEN_KEY, "refresh-shared");
    let refreshCalls = 0;
    const f = makeFetch((url, init) => {
      const auth = (init?.headers as Record<string, string> | undefined)?.["Authorization"];
      if (url.endsWith("/auth/refresh")) {
        refreshCalls += 1;
        return json({ token: "tok-shared-fresh", refresh_token: "refresh-shared-next" });
      }
      if (url.includes("/workflow-drafts/") && auth === "Bearer tok-shared-fresh") {
        return json({ id: url.endsWith("/one") ? "one" : "two" });
      }
      if (url.includes("/workflow-drafts/")) {
        return json({ detail: { error_code: "TOKEN_EXPIRED" } }, 401);
      }
      return json({}, 404);
    });
    globalThis.fetch = f;

    const drafts = await import("./drafts");
    const [one, two] = await Promise.all([drafts.getDraft("one"), drafts.getDraft("two")]);

    expect(one.id).toBe("one");
    expect(two.id).toBe("two");
    expect(refreshCalls).toBe(1);
  });
});
