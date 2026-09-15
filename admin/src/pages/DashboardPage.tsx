import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/Layout";
import { ErrorNote, Panel, Stat, StatusChip } from "../components/Panel";
import { listOrders, listProducts } from "../lib/api";
import { formatDateTime, formatMoney, orderStatusLabel, orderStatusTone } from "../lib/format";

const ORDER_STATUSES = [
  "awaiting_payment",
  "paid",
  "fulfilled",
  "completed",
  "cancelled",
  "refunded",
] as const;

export function DashboardPage() {
  const products = useQuery({
    queryKey: ["products", "dashboard"],
    queryFn: () => listProducts({ limit: 200 }),
  });

  const orders = useQuery({
    queryKey: ["orders", "dashboard"],
    queryFn: () => listOrders({ limit: 200 }),
  });

  const error = products.error ?? orders.error;
  const rows = orders.data?.items ?? [];

  // Revenue counts money that has actually been captured, not carts that were
  // abandoned at the payment step — so cancelled and unpaid orders are excluded.
  const revenueByCurrency = new Map<string, number>();
  for (const order of rows) {
    if (!["paid", "fulfilled", "completed"].includes(order.status)) continue;
    revenueByCurrency.set(
      order.currency_code,
      (revenueByCurrency.get(order.currency_code) ?? 0) + Number(order.total),
    );
  }

  const counts = ORDER_STATUSES.map((status) => ({
    status,
    count: rows.filter((order) => order.status === status).length,
  })).filter((row) => row.count > 0);

  const lowStock = (products.data?.items ?? [])
    .flatMap((product) =>
      product.variants.map((variant) => ({ product, variant })),
    )
    .filter((row) => row.variant.available <= 5)
    .slice(0, 8);

  return (
    <>
      <PageHeader
        description="上架情况、订单水位与低库存提醒。"
        title="概览"
      />

      <ErrorNote error={error} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          hint={products.isLoading ? "加载中…" : undefined}
          label="商品"
          value={String(products.data?.total ?? 0)}
        />
        <Stat
          hint={orders.isLoading ? "加载中…" : undefined}
          label="订单"
          value={String(orders.data?.total ?? 0)}
        />
        <Stat
          hint={counts.map((row) => `${orderStatusLabel(row.status)} ${row.count}`).join(" · ") || "—"}
          label="待处理"
          value={String(
            counts
              .filter((row) => row.status === "awaiting_payment" || row.status === "paid")
              .reduce((sum, row) => sum + row.count, 0),
          )}
        />
        <Stat
          hint="已支付及之后的订单合计"
          label="已确认收入"
          value={
            revenueByCurrency.size === 0
              ? "—"
              : [...revenueByCurrency.entries()]
                  .map(([currency, amount]) => formatMoney(String(amount), currency))
                  .join("  ")
          }
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel
          actions={
            <Link className="text-xs text-neon-cyan hover:underline" to="/orders">
              全部订单
            </Link>
          }
          title="最近订单"
        >
          {rows.length === 0 ? (
            <p className="text-sm text-slate-500">还没有订单。</p>
          ) : (
            <ul className="space-y-2">
              {rows.slice(0, 6).map((order) => (
                <li key={order.id} className="flex items-center justify-between gap-3 text-sm">
                  <Link
                    className="font-mono text-xs text-neon-cyan hover:underline"
                    to={`/orders/${order.number}`}
                  >
                    {order.number}
                  </Link>
                  <span className="text-xs text-slate-500">
                    {formatDateTime(order.events[0]?.created_at)}
                  </span>
                  <StatusChip
                    label={orderStatusLabel(order.status)}
                    tone={orderStatusTone(order.status)}
                  />
                  <span className="w-24 text-right font-semibold text-slate-200">
                    {formatMoney(order.total, order.currency_code)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="低库存（≤ 5）">
          {lowStock.length === 0 ? (
            <p className="text-sm text-slate-500">没有低库存变体。</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {lowStock.map(({ product, variant }) => (
                <li className="flex items-center justify-between gap-3" key={variant.id}>
                  <span className="truncate text-slate-200">
                    {product.translations[0]?.name ?? product.id.slice(0, 8)}
                    <span className="ml-2 font-mono text-xs text-slate-500">{variant.sku}</span>
                  </span>
                  <span
                    className={variant.available === 0 ? "text-red-300" : "text-warning"}
                  >
                    可用 {variant.available}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}
