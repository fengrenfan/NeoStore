import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PayButton } from "@/components/PayButton";
import { ApiError, getOrder } from "@/lib/api";
import { formatDateTime, formatMoney, orderStatusLabel } from "@/lib/format";
import { copy } from "@/lib/strings";
import type { Order } from "@/lib/types";

export const metadata: Metadata = {
  title: "Order",
  robots: { index: false, follow: false },
};

/** `null` only for a genuinely missing order; anything else must surface. */
async function fetchOrder(number: string): Promise<Order | null> {
  try {
    return await getOrder(number);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export default async function OrderPage({
  params,
}: {
  params: Promise<{ locale: string; number: string }>;
}) {
  const { locale, number } = await params;
  const t = copy(locale);
  const order = await fetchOrder(number);
  if (!order) notFound();

  const currency = order.currency_code;
  const address = order.shipping_address as Record<string, string>;
  // The order carries no `created_at`, but its first event is the checkout.
  const placedAt = order.events[0]?.created_at;

  return (
    <div className="space-y-8">
      <header className="surface space-y-3 p-6">
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="text-xl font-bold text-slate-100">{t.orderTitle}</h1>
          <span className="font-mono text-sm text-neon-cyan">{order.number}</span>
          <span className="pill ml-auto">{orderStatusLabel(order.status, locale)}</span>
        </div>
        <p className="text-sm text-slate-300">{t.orderThanks(order.email)}</p>
        {placedAt ? (
          <p className="text-xs text-slate-500">
            {t.orderPlaced} · {formatDateTime(placedAt, locale)}
          </p>
        ) : null}
        {order.status === "awaiting_payment" ? (
          <PayButton
            labels={{
              pay: t.simulatePayment,
              paying: t.simulating,
              failed: t.somethingWentWrong,
            }}
            number={order.number}
          />
        ) : null}
        {order.status === "paid" ? (
          <p className="text-sm text-positive">{t.paymentConfirmed}</p>
        ) : null}
      </header>

      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            {t.description}
          </h2>
          <ul className="space-y-2">
            {order.lines.map((line, index) => (
              <li
                className="surface flex flex-wrap items-baseline gap-3 p-4"
                key={`${line.sku}-${index}`}
              >
                <div className="min-w-40 flex-1">
                  <p className="text-sm text-slate-100">{line.product_name}</p>
                  <p className="text-xs text-slate-500">
                    {[line.variant_label, `${t.sku} ${line.sku}`].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <span className="text-xs text-slate-400">
                  {formatMoney(line.unit_price, line.currency_code, locale)} × {line.quantity}
                </span>
                <span className="w-24 text-right text-sm font-semibold text-slate-100">
                  {formatMoney(line.line_total, line.currency_code, locale)}
                </span>
              </li>
            ))}
          </ul>

          {order.events.length > 0 ? (
            <section className="surface space-y-2 p-4">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {t.orderStatus}
              </h2>
              <ol className="space-y-2 text-xs">
                {order.events.map((event, index) => (
                  <li className="flex flex-wrap gap-2 text-slate-400" key={index}>
                    <span className="text-slate-200">
                      {orderStatusLabel(event.to_status, locale)}
                    </span>
                    <span>{formatDateTime(event.created_at, locale)}</span>
                    {event.note ? (
                      <span className="font-mono text-slate-500">{event.note}</span>
                    ) : null}
                  </li>
                ))}
              </ol>
            </section>
          ) : null}
        </section>

        <aside className="space-y-4">
          <div className="surface space-y-2 p-5 text-sm">
            <dl className="space-y-2">
              <div className="flex justify-between gap-4">
                <dt className="text-slate-400">{t.subtotal}</dt>
                <dd className="text-slate-200">{formatMoney(order.subtotal, currency, locale)}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-400">{t.shipping}</dt>
                <dd className="text-slate-200">
                  {Number(order.shipping_fee) === 0
                    ? t.free
                    : formatMoney(order.shipping_fee, currency, locale)}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-400">{t.tax}</dt>
                <dd className="text-slate-200">{formatMoney(order.tax, currency, locale)}</dd>
              </div>
              <div className="flex justify-between gap-4 border-t border-ink-line pt-2">
                <dt className="text-slate-200">{t.total}</dt>
                <dd className="font-semibold text-white">
                  {formatMoney(order.total, currency, locale)}
                </dd>
              </div>
            </dl>
          </div>

          <div className="surface space-y-1 p-5 text-sm text-slate-300">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {t.fullName}
            </p>
            <p>{address.name}</p>
            <p>{address.line1}</p>
            {address.line2 ? <p>{address.line2}</p> : null}
            <p>
              {[address.city, address.postal_code].filter(Boolean).join(" ")}
            </p>
            <p>{address.country}</p>
          </div>

          <Link className="btn-ghost w-full" href={`/${locale}/products`}>
            {t.backToShop}
          </Link>
        </aside>
      </div>
    </div>
  );
}
