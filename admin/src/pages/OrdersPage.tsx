import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/Layout";
import { EmptyRow, ErrorNote, Panel, StatusChip } from "../components/Panel";
import { listOrders } from "../lib/api";
import { formatDateTime, formatMoney, orderStatusLabel, orderStatusTone } from "../lib/format";

const FILTERS = [
  { value: "", label: "全部" },
  { value: "awaiting_payment", label: "待支付" },
  { value: "paid", label: "已支付" },
  { value: "fulfilled", label: "已发货" },
  { value: "completed", label: "已完成" },
  { value: "cancelled", label: "已取消" },
  { value: "refunded", label: "已退款" },
];

export function OrdersPage() {
  const [status, setStatus] = useState("");

  const orders = useQuery({
    queryKey: ["orders", status],
    queryFn: () => listOrders({ status: status || undefined, limit: 100 }),
  });

  const rows = orders.data?.items ?? [];

  return (
    <>
      <PageHeader
        description="订单状态只能沿状态机流转，每次变更都会写入审计事件。"
        title="订单"
      />

      <ErrorNote error={orders.error} />

      <div className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map((filter) => (
          <button
            className={`rounded-xl border px-3 py-1.5 text-xs transition ${
              status === filter.value
                ? "border-neon-violet bg-neon-violet/10 text-white"
                : "border-ink-line text-slate-300 hover:border-neon-violet/60"
            }`}
            key={filter.value}
            onClick={() => setStatus(filter.value)}
            type="button"
          >
            {filter.label}
          </button>
        ))}
      </div>

      <Panel title={`${orders.data?.total ?? 0} 笔订单`}>
        {orders.isLoading ? (
          <p className="text-sm text-slate-400">加载中…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>订单号</th>
                <th>状态</th>
                <th>地区</th>
                <th>邮箱</th>
                <th>下单时间</th>
                <th className="text-right">金额</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <EmptyRow colSpan={6}>没有符合条件的订单。</EmptyRow>
              ) : (
                rows.map((order) => (
                  <tr key={order.id}>
                    <td>
                      <Link
                        className="font-mono text-xs text-neon-cyan hover:underline"
                        to={`/orders/${order.number}`}
                      >
                        {order.number}
                      </Link>
                    </td>
                    <td>
                      <StatusChip
                        label={orderStatusLabel(order.status)}
                        tone={orderStatusTone(order.status)}
                      />
                    </td>
                    <td className="text-xs uppercase text-slate-400">{order.region_code}</td>
                    <td className="text-xs text-slate-400">{order.email}</td>
                    <td className="text-xs text-slate-400">
                      {formatDateTime(order.events[0]?.created_at)}
                    </td>
                    <td className="text-right font-semibold text-slate-100">
                      {formatMoney(order.total, order.currency_code)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </Panel>
    </>
  );
}
