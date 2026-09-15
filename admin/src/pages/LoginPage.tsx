import { useState } from "react";

import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";

export function LoginPage() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("admin@neostore.local");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 401
          ? "邮箱或密码不正确。"
          : "无法登录，请检查后端服务是否可用。",
      );
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form className="surface w-full max-w-sm space-y-5 p-8" onSubmit={submit}>
        <div className="space-y-1 text-center">
          <p className="text-2xl font-bold neon-text">NeoStore</p>
          <p className="text-xs uppercase tracking-wide text-slate-500">管理控制台</p>
        </div>

        <label className="block">
          <span className="field-label">邮箱</span>
          <input
            autoComplete="username"
            className="field"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
        </label>

        <label className="block">
          <span className="field-label">密码</span>
          <input
            autoComplete="current-password"
            className="field"
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </label>

        {error ? <p className="text-sm text-red-400">{error}</p> : null}

        <button className="btn-primary w-full" disabled={busy} type="submit">
          {busy ? "登录中…" : "登录"}
        </button>

        <p className="text-center text-[11px] text-slate-500">
          演示账号由 <code className="text-slate-400">app.seed</code> 创建
        </p>
      </form>
    </div>
  );
}
