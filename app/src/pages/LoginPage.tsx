import { useState } from "react";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email || !password) { setError("请输入邮箱和密码"); return; }
    setBusy(true);
    try {
      const r = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.message || data.detail || ("HTTP " + r.status));
      localStorage.setItem("fliki-auth-token", data.token);
      if (data.refresh_token) localStorage.setItem("fliki-auth-refresh-token", data.refresh_token);
      window.location.href = "/drafts.html";
    } catch (e) {
      setError(e instanceof Error ? e.message : "登录失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <a className="logo" href="/index.html"><span className="dot"></span>本地视频制作台</a>
      <h1>欢迎回来</h1>
      <p className="sub">登录继续编辑你的视频草稿.</p>
      <form onSubmit={submit}>
        <label>邮箱</label>
        <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>密码</label>
        <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <div className="err">{error}</div>}
        <button className="submit" type="submit" disabled={busy}>{busy ? "登录中..." : "登录"}</button>
      </form>
      <div className="alt">还没有账号? <a href="/signup.html">免费注册</a></div>
    </div>
  );
}

export default LoginPage;
