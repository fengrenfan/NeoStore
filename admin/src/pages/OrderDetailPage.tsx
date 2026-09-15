import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "../components/Layout";
import { ErrorNote, Panel, StatusChip } from "../components/Panel";
import { getOrder, orderTransitions, updateOrderStatus } from "../lib/api";
import { formatDateTime, formatMoney, orderStatusLabel, orderStatusTone } from "../lib/format";

/**
 * Order detail with the status machine exposed as buttons.
 *
 * The available targets come from `GET /orders/{ref}/transitions` rather than
 * being reimplemented here: the backend owns the state machine, and duplicating
 * it in the UI is how the two drift apart.
 */
export function OrderDetailPage() {
  const { ref = "" } = useParams();
  const queryClient = useQueryClient();

  const order = useQuery({ queryKey: ["order", ref], queryFn: () => getOrder(ref) });
  const transitions = useQuery({
    queryKey: ["order", ref, "transitions"],
    queryFn: () => orderTransitions(ref),
    enabled: Boolean(ref),
  });

  const transition = useMutation({
    mutationFn: (target: string) => updateOrderStatus(ref, target),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["order", ref] });
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });

  if (order.isLoading) {
    return <p className="text-sm text-slate-400">加载中…</p>;
  }

  if (order.error || !order.data) {
    return (
      <>
        <PageHeader title="订单" />
        <ErrorNote error={order.error ?? new Error("订单不存在")} />
        <Link className="btn-ghost mt-4" to="/orders">
          返回订单列表
        </Link>
      </>
    );
  }

  const data = order.data;
  const address = data.shipping_address as Record<string, string | undefined>;
  const currency = data.currency_code;

  return (
    <>
      <PageHeader
        actions={
          <Link className="btn-ghost" to="/orders">
            返回列表
          </Link>
        }
        description={`地区 ${data.region_code.toUpperCase()} · 下单邮箱 ${data.email}`}
        title={`订单 ${data.number}`}
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <StatusChip
          label={orderStatusLabel(data.status)}
          tone={orderStatusTone(data.status)}
        />
        {(transitions.data ?? []).map((target) => (
          <button
            className={target === "cancelled" ? "btn-danger" : "btn-primary"}
            disabled={transition.isPending}
            key={target}
            onClick={() => transition.mutate(target)}
            type="button"
          >
            转为「{orderStatusLabel(target)}」
          </button>
        ))}
      </div>

      <ErrorNote error={transition.error} />

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <Panel title="商品行（下单时快照）">
            <table>
              <thead>
                <tr>
                  <th>商品</th>
                  <th>SKU</th>
                  <th>单价</th>
                  <th>数量</th>
                  <th className="text-right">小计</th>
                </tr>
              </thead>
              <tbody>
                {data.lines.map((line, index) => (
                  <tr key={`${line.sku}-${index}`}>
                    <td>
                      <p className="text-slate-100">{line.product_name}</p>
                      {line.variant_label ? (
                        <p className="text-xs text-slate-500">{line.variant_label}</p>
                      ) : null}
                    </td>
                    <td className="font-mono text-xs text-slate-400">{line.sku}</td>
                    <td className="text-slate-300">
                      {formatMoney(line.unit_price, line.currency_code)}
                    </td>
                    <td className="text-slate-300">{line.quantity}</td>
                    <td className="text-right text-slate-100">
                      {formatMoney(line.line_total, line.currency_code)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Panel title="状态事件（审计）">
            <ol className="space-y-3">
              {data.events.map((event, index) => (
                <li className="flex flex-wrap items-baseline gap-3 text-sm" key={index}>
                  <span className="text-slate-200">
                    {event.from_status ? `${orderStatusLabel(event.from_status)} → ` : ""}
                    {orderStatusLabel(event.to_status)}
                  </span>
                  <span className="text-xs text-slate-500">
                    {formatDateTime(event.created_at)}
                  </span>
                  {event.note ? (
                    <span className="font-mono text-xs text-slate-500">{event.note}</span>
                  ) : null}
                </li>
              ))}
            </ol>
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="金额">
            <dl className="space-y-2 text-sm">
              {[
                ["商品小计", data.subtotal],
                ["运费", data.shipping_fee],
                ["税费", data.tax],
              ].map(([label, value]) => (
                <div className="flex justify-between gap-4" key={label}>
                  <dt className="text-slate-400">{label}</dt>
                  <dd className="text-slate-200">{formatMoney(String(value), currency)}</dd>
                </div>
              ))}
              <div className="flex justify-between gap-4 border-t border-ink-line pt-2">
                <dt className="text-slate-200">合计</dt>
                <dd className="font-semibold text-white">{formatMoney(data.total, currency)}</dd>
              </div>
            </dl>
          </Panel>

          <Panel title="收货地址">
            <address className="space-y-1 text-sm not-italic text-slate-300">
              <p className="text-slate-100">{address.name}</p>
              <p>{address.line1}</p>
              {address.line2 ? <p>{address.line2}</p> : null}
              <p>{[address.city, address.postal_code].filter(Boolean).join(" ")}</p>
              <p>{address.country}</p>
            </address>
          </Panel>
        </div>
      </div>
    </>
  );
}
