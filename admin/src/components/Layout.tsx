import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../lib/auth";

const NAV = [
  { to: "/", label: "概览", end: true },
  { to: "/products", label: "商品" },
  { to: "/orders", label: "订单" },
  { to: "/inventory", label: "库存" },
  { to: "/settings", label: "设置" },
];

export function Layout() {
  const { profile, signOut } = useAuth();

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r border-ink-line bg-ink-raised">
        <div className="border-b border-ink-line px-5 py-5">
          <p className="text-lg font-bold neon-text">NeoStore</p>
          <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-500">控制台</p>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              className={({ isActive }) =>
                `block rounded-xl px-3 py-2 text-sm transition ${
                  isActive
                    ? "bg-neon-violet/15 text-white"
                    : "text-slate-300 hover:bg-ink hover:text-white"
                }`
              }
              end={item.end}
              to={item.to}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="space-y-2 border-t border-ink-line p-4 text-xs text-slate-400">
          <p className="truncate" title={profile?.email}>
            {profile?.email ?? "—"}
          </p>
          <p className="pill">{profile?.role ?? "—"}</p>
          <button className="btn-ghost w-full" onClick={signOut} type="button">
            退出登录
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-x-hidden px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}

/** Shared page chrome: heading plus an optional action slot. */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-xl font-bold text-slate-100">{title}</h1>
        {description ? <p className="mt-1 text-sm text-slate-400">{description}</p> : null}
      </div>
      {actions}
    </header>
  );
}
