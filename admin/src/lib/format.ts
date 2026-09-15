/**
 * Display helpers.
 *
 * Parsing a money string into a `number` is fine here because this is rendering
 * only — every calculation happens on the backend with `Decimal`.
 */

export function formatMoney(amount: string, currency: string, locale = "zh-CN"): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return `${amount} ${currency}`;
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency }).format(value);
  } catch {
    return `${amount} ${currency}`;
  }
}

export function formatDateTime(iso: string | null | undefined, locale = "zh-CN"): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

const ORDER_STATUS: Record<string, string> = {
  draft: "草稿",
  awaiting_payment: "待支付",
  paid: "已支付",
  fulfilled: "已发货",
  completed: "已完成",
  cancelled: "已取消",
  refunded: "已退款",
};

const PRODUCT_STATUS: Record<string, string> = {
  draft: "草稿",
  active: "上架",
  archived: "下架",
};

export function orderStatusLabel(status: string): string {
  return ORDER_STATUS[status] ?? status;
}

export function productStatusLabel(status: string): string {
  return PRODUCT_STATUS[status] ?? status;
}

/** Tailwind classes for a status chip, keyed off the status machine. */
export function orderStatusTone(status: string): string {
  switch (status) {
    case "paid":
    case "completed":
      return "border-positive/40 text-positive";
    case "awaiting_payment":
      return "border-warning/40 text-warning";
    case "cancelled":
    case "refunded":
      return "border-red-500/40 text-red-300";
    case "fulfilled":
      return "border-neon-cyan/40 text-neon-cyan";
    default:
      return "border-ink-line text-slate-300";
  }
}

export function productStatusTone(status: string): string {
  switch (status) {
    case "active":
      return "border-positive/40 text-positive";
    case "draft":
      return "border-warning/40 text-warning";
    default:
      return "border-ink-line text-slate-400";
  }
}
