import { useState } from "react";

function strengthOf(p: string): { score: number; label: string; color: string } {
  let score = 0;
  if (p.length >= 8) score++;
  if (p.length >= 12) score++;
  if (/[A-Z]/.test(p) && /[a-z]/.test(p)) score++;
  if (/[0-9]/.test(p)) score++;
  if (/[^A-Za-z0-9]/.test(p)) score++;
  const labels = ["太弱", "较弱", "一般", "良好", "强", "很强"];
  const colors = ["#dc5050", "#dc5050", "#d8a84a", "#48d58b", "#48d58b", "#48d58b"];
  return { score, label: labels[score], color: colors[score] };
}

export function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const pw = strengthOf(password);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setOk(null);
    if (!email || !password) { setError("请填写邮箱和密码"); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError("邮箱格式不对"); return; }
    if (password.length < 8) { setError("密码至少 8 位"); return; }
    if (password !== confirm) { setError("两次密码不一致"); return; }
    setBusy(true);
    try {
      const r = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password, role: "user" }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.message || data.detail || ("HTTP " + r.status));
      setOk("注册成功, 跳转登录...");
      setTimeout(() => { window.location.href = "/login.html"; }, 700);
    } catch (e) {
      setError(e instanceof Error ? e.message : "注册失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <a className="logo" href="/index.html"><span className="dot"></span>本地视频制作台</a>
      <h1>免费注册</h1>
      <p className="sub">无需信用卡, 30 秒开始第一条视频.</p>
      <form onSubmit={submit}>
        <label>邮箱</label>
        <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>密码 (至少 8 位)</label>
        <input type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        <div className="strength"><div style={{ width: ((pw.score / 5) * 100) + "%", background: pw.color }}></div></div>
        <small style={{ color: pw.color, fontSize: 11, display: "block", marginTop: 4 }}>{pw.label}</small>
        <label>确认密码</label>
        <input type="password" autoComplete="new-password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        {error && <div className="err">{error}</div>}
        {ok && <div className="ok">{ok}</div>}
        <button className="submit" type="submit" disabled={busy}>{busy ? "注册中..." : "免费注册"}</button>
      </form>
      <div className="alt">已有账号? <a href="/login.html">登录</a></div>
    </div>
  );
}

export default SignupPage;
