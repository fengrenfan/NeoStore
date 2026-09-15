/**
 * Display formatting.
 *
 * Parsing an amount string into a `number` is safe *here* because this is only
 * ever used for rendering. Every arithmetic operation on money happens on the
 * backend with `Decimal` — never in the browser.
 */

export function formatMoney(amount: string, currency: string, locale: string): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return `${amount} ${currency}`;
  try {
    // `Intl` already knows JPY has no minor unit, so no special-casing here.
    return new Intl.NumberFormat(locale, { style: "currency", currency }).format(value);
  } catch {
    return `${amount} ${currency}`;
  }
}

export function formatDateTime(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

/** Human labels for the order status machine. */
const ORDER_STATUS_LABELS: Record<string, { zh: string; en: string }> = {
  draft: { zh: "草稿", en: "Draft" },
  awaiting_payment: { zh: "待支付", en: "Awaiting payment" },
  paid: { zh: "已支付", en: "Paid" },
  fulfilled: { zh: "已发货", en: "Fulfilled" },
  completed: { zh: "已完成", en: "Completed" },
  cancelled: { zh: "已取消", en: "Cancelled" },
  refunded: { zh: "已退款", en: "Refunded" },
};

export function orderStatusLabel(status: string, locale: string): string {
  const labels = ORDER_STATUS_LABELS[status];
  if (!labels) return status;
  return locale.startsWith("zh") ? labels.zh : labels.en;
}

export function isOrderComplete(status: string): boolean {
  return status === "completed" || status === "fulfilled";
}
