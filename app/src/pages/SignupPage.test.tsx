import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SignupPage } from "./SignupPage";

let lastFetch: { url: string; init: RequestInit } | null = null;
beforeEach(() => {
  lastFetch = null;
  try { localStorage.clear(); } catch {}
  let _href = "";
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      get href() { return _href; },
      set href(v: string) { _href = String(v); (window as any).__lastHref = String(v); },
    },
  });
  vi.clearAllTimers();
  vi.useRealTimers();
  (window as any).__lastHref = "";
});

function mockFetchOnce(responder: (url: string, init: RequestInit) => Promise<Response> | Response) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    lastFetch = { url, init: init || {} };
    return Promise.resolve(responder(url, init || {}));
  });
}

function setValidCreds() {
  fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "user@example.com" } });
  fireEvent.change(screen.getByLabelText("密码 (至少 8 位)"), { target: { value: "Abcd1234!" } });
  fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "Abcd1234!" } });
}

describe("SignupPage R9 (rev38)", () => {
  it("renders 3 inputs + submit button + login link", () => {
    render(<SignupPage />);
    expect(screen.getByLabelText("邮箱")).toBeTruthy();
    expect(screen.getByLabelText("密码 (至少 8 位)")).toBeTruthy();
    expect(screen.getByLabelText("确认密码")).toBeTruthy();
    expect(screen.getByRole("button", { name: /免费注册/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: /登录/ }).getAttribute("href")).toBe("/login.html");
  });

  it("empty submit -> 请填写邮箱和密码", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(new Response("{}")));
    const { container } = render(<SignupPage />);
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(container.querySelector(".err")?.textContent).toBe("请填写邮箱和密码");
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("invalid email -> 邮箱格式不对", async () => {
    const { container } = render(<SignupPage />);
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "not-an-email" } });
    fireEvent.change(screen.getByLabelText("密码 (至少 8 位)"), { target: { value: "Abcd1234!" } });
    fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "Abcd1234!" } });
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(container.querySelector(".err")?.textContent).toBe("邮箱格式不对");
    });
  });

  it("password < 8 chars -> 密码至少 8 位", async () => {
    const { container } = render(<SignupPage />);
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "u@e.c" } });
    fireEvent.change(screen.getByLabelText("密码 (至少 8 位)"), { target: { value: "short" } });
    fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "short" } });
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(container.querySelector(".err")?.textContent).toBe("密码至少 8 位");
    });
  });

  it("password != confirm -> 两次密码不一致", async () => {
    const { container } = render(<SignupPage />);
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "u@e.c" } });
    fireEvent.change(screen.getByLabelText("密码 (至少 8 位)"), { target: { value: "Abcd1234!" } });
    fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "DIFFERENT" } });
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(container.querySelector(".err")?.textContent).toBe("两次密码不一致");
    });
  });

  it("password strength bar: weak (abc) -> strong (Abcd1234!)", async () => {
    const { container } = render(<SignupPage />);
    const pwInput = screen.getByLabelText("密码 (至少 8 位)");
    const strengthSmall = container.querySelector(".strength + small") as HTMLElement | null;
    fireEvent.change(pwInput, { target: { value: "abc" } });
    await waitFor(() => { expect(strengthSmall?.textContent).toMatch(/太弱|较弱/); });
    fireEvent.change(pwInput, { target: { value: "Abcd1234!" } });
    await waitFor(() => { expect(strengthSmall?.textContent).toMatch(/强|很强/); });
  });

  it("valid submit -> POST /auth/register + role=user + lowercase email", async () => {
    mockFetchOnce(() => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const { container } = render(<SignupPage />);
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: " User@Example.COM " } });
    fireEvent.change(screen.getByLabelText("密码 (至少 8 位)"), { target: { value: "Abcd1234!" } });
    fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "Abcd1234!" } });
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => { expect(lastFetch).not.toBeNull(); });
    expect(lastFetch!.url).toBe("/auth/register");
    expect(lastFetch!.init.method).toBe("POST");
    const body = JSON.parse(String(lastFetch!.init.body));
    expect(body.email).toBe("user@example.com");
    expect(body.password).toBe("Abcd1234!");
    expect(body.role).toBe("user");
  });

  it("success -> ok message + redirect to /login.html after 700ms", async () => {
    mockFetchOnce(() => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const { container } = render(<SignupPage />);
    setValidCreds();
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(container.querySelector(".ok")?.textContent).toMatch(/注册成功/);
    });
    expect((window as any).__lastHref || "").toBe("");
    await new Promise<void>((r) => setTimeout(r, 800));
    expect((window as any).__lastHref).toBe("/login.html");
  });

  it("HTTP 409 (email taken) -> inline error, no redirect", async () => {
    mockFetchOnce(() => new Response(JSON.stringify({ message: "邮箱已被注册" }), { status: 409 }));
    const { container } = render(<SignupPage />);
    setValidCreds();
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(container.querySelector(".err")?.textContent).toMatch(/邮箱已被注册|HTTP 409/);
    });
    expect((window as any).__lastHref || "").toBe("");
  });
});
