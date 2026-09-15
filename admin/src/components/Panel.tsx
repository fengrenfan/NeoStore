/** Small shared presentational pieces. */

export function Panel({
  title,
  children,
  actions,
}: {
  title?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <section className="surface">
      {title ? (
        <header className="flex items-center justify-between gap-3 border-b border-ink-line px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-200">{title}</h2>
          {actions}
        </header>
      ) : null}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="surface p-5">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-bold text-slate-100">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function StatusChip({
  label,
  tone,
}: {
  label: string;
  tone: string;
}) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs ${tone}`}>
      {label}
    </span>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  const message =
    error instanceof Error ? `${error.message}` : "请求失败，请稍后重试。";
  return (
    <p className="rounded-xl border border-red-500/40 bg-red-500/5 px-3 py-2 text-sm text-red-300">
      {message}
    </p>
  );
}

export function EmptyRow({ colSpan, children }: { colSpan: number; children: React.ReactNode }) {
  return (
    <tr>
      <td className="px-3 py-8 text-center text-sm text-slate-500" colSpan={colSpan}>
        {children}
      </td>
    </tr>
  );
}
