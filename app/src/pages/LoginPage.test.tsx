import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { LoginPage } from "./LoginPage";

let lastFetch: { url: string; init: RequestInit } | null = null;
beforeEach(() => {
  lastFetch = null;
  try { localStorage.clear(); } catch {}
  try { sessionStorage.clear(); } catch {}
  // jsdom 下 window.location 是 read-only, 用 defineProperty setter 拦 href 写入
  let _href = "";
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      get href() { return _href; },
      set href(v: string) { _href = String(v); (window as any).__lastHref = String(v); },
    },
  });
});

function mockFetchOnce(responder: (url: string, init: RequestInit) => Promise<Response> | Response) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    lastFetch = { url, init: init || {} };
    return Promise.resolve(responder(url, init || {}));
  });
}

describe("LoginPage R8 (rev38)", () => {
  it("renders email + password inputs + submit button + signup link", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("邮箱")).toBeTruthy();
    expect(screen.getByLabelText("密码")).toBeTruthy();
    expect(screen.getByRole("button", { name: /登录/ })).toBeTruthy();
    const signup = screen.getByRole("link", { name: /免费注册/ });
    expect(signup.getAttribute("href")).toBe("/signup.html");
  });

  it("empty submit -> inline error 请输入邮箱和密码 (no fetch)", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(new Response("{}")));
    const { container } = render(<LoginPage />);
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(document.querySelector(".err")?.textContent).toBe("请输入邮箱和密码");
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("valid submit -> POST /auth/login + body lowercase email", async () => {
    mockFetchOnce(() => new Response(JSON.stringify({ token: "T1", refresh_token: "R1" }), { status: 200 }));
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "User@Example.COM " } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret123" } });
    fireEvent.submit(document.querySelector("form")!);
    await waitFor(() => {
      expect(lastFetch).not.toBeNull();
    });
    expect(lastFetch!.url).toBe("/auth/login");
    expect(lastFetch!.init.method).toBe("POST");
    const body = JSON.parse(String(lastFetch!.init.body));
    expect(body.email).toBe("user@example.com");
    expect(body.password).toBe("secret123");
  });

  it("success -> store fliki-auth-token + redirect", async () => {
    mockFetchOnce(() => new Response(JSON.stringify({ token: "T-abc", refresh_token: "R-xyz" }), { status: 200 }));
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@b.c" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "pw" } });
    fireEvent.submit(document.querySelector("form")!);
    await waitFor(() => {
      expect(localStorage.getItem("fliki-auth-token")).toBe("T-abc");
      expect(localStorage.getItem("fliki-auth-refresh-token")).toBe("R-xyz");
      expect((window as any).__lastHref || "").toBe("/drafts.html");
    });
  });

  it("HTTP 401 -> inline error message + no redirect + no token", async () => {
    mockFetchOnce(() => new Response(JSON.stringify({ message: "邮箱或密码错误" }), { status: 401 }));
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@b.c" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "wrong" } });
    fireEvent.submit(document.querySelector("form")!);
    await waitFor(() => {
      expect(document.querySelector(".err")?.textContent).toMatch(/邮箱或密码错误|HTTP 401/);
    });
    expect((window as any).location.href).toBe("");
    expect(localStorage.getItem("fliki-auth-token")).toBeNull();
  });

  it("HTTP 500 with non-JSON body -> generic HTTP <status> error", async () => {
    mockFetchOnce(() => new Response("internal error plain text", { status: 500 }));
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@b.c" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "pw" } });
    fireEvent.submit(document.querySelector("form")!);
    await waitFor(() => {
      expect(document.querySelector(".err")?.textContent).toMatch(/HTTP 500|登录失败/);
    });
  });

  it("submit button toggles 登录中... -> 登录 (busy state)", async () => {
    let resolveFetch: (v: Response) => void = () => {};
    vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise<Response>((res) => { resolveFetch = res; }));
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@b.c" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "pw" } });
    fireEvent.submit(document.querySelector("form")!);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /登录中/ })).toBeDisabled();
    });
    resolveFetch(new Response(JSON.stringify({ token: "T" }), { status: 200 }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /^登录$/ })).toBeEnabled();
    });
  });
});
