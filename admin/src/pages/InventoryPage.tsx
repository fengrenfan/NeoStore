import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { PageHeader } from "../components/Layout";
import { EmptyRow, ErrorNote, Panel, StatusChip } from "../components/Panel";
import { adjustInventory, getInventory, listProducts } from "../lib/api";
import type { AdminProduct, AdminVariant } from "../lib/types";

/** Anything at or below this is worth an operator's attention. */
const LOW_STOCK = 5;

interface VariantRow {
  variant: AdminVariant;
  productName: string;
  productStatus: string;
}

export function InventoryPage() {
  const [query, setQuery] = useState("");
  const [lowOnly, setLowOnly] = useState(false);

  // There is no "list every inventory item" endpoint on purpose — inventory is
  // always reached through a variant. So we enumerate variants from the
  // catalogue and let each row query its own stock record.
  const products = useQuery({
    queryKey: ["products"],
    queryFn: () => listProducts({ limit: 100 }),
  });

  const rows = useMemo<VariantRow[]>(() => {
    const items: AdminProduct[] = products.data?.items ?? [];
    return items.flatMap((product) => {
      const primary =
        product.translations.find((row) => row.locale === "zh-CN") ?? product.translations[0];
      return product.variants.map((variant) => ({
        variant,
        productName: primary?.name ?? "（未命名）",
        productStatus: product.status,
      }));
    });
  }, [products.data]);

  const needle = query.trim().toLowerCase();
  const visible = rows.filter((row) => {
    if (needle) {
      const haystack = `${row.productName} ${row.variant.sku}`.toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    if (lowOnly && row.variant.available > LOW_STOCK) return false;
    return true;
  });

  const totalAvailable = rows.reduce((sum, row) => sum + row.variant.available, 0);
  const lowCount = rows.filter((row) => row.variant.available <= LOW_STOCK).length;

  return (
    <>
      <PageHeader
        description={`在每个变体上做增减。低于 ${LOW_STOCK} 件会标红——预留中的库存已经算在可用量之外。`}
        title="库存"
      />

      <ErrorNote error={products.error} />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <div className="surface p-5">
          <p className="text-xs uppercase tracking-wide text-slate-400">变体总数</p>
          <p className="mt-2 text-2xl font-bold text-slate-100">{rows.length}</p>
        </div>
        <div className="surface p-5">
          <p className="text-xs uppercase tracking-wide text-slate-400">可用合计</p>
          <p className="mt-2 text-2xl font-bold text-slate-100">{totalAvailable}</p>
        </div>
        <div className="surface p-5">
          <p className="text-xs uppercase tracking-wide text-slate-400">低库存变体</p>
          <p className={`mt-2 text-2xl font-bold ${lowCount > 0 ? "text-warning" : "text-slate-100"}`}>
            {lowCount}
          </p>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          className="field w-64"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="按商品名或 SKU 搜索"
          value={query}
        />
        <button
          className={`rounded-xl border px-3 py-2 text-xs transition ${
            lowOnly
              ? "border-neon-violet bg-neon-violet/10 text-white"
              : "border-ink-line text-slate-300 hover:border-neon-violet/60"
          }`}
          onClick={() => setLowOnly((current) => !current)}
          type="button"
        >
          只看低库存
        </button>
        <span className="text-xs text-slate-500">共 {visible.length} 个变体</span>
      </div>

      <Panel title="变体库存">
        {products.isLoading ? (
          <p className="text-sm text-slate-400">加载中…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>商品</th>
                <th>SKU</th>
                <th className="text-right">在库</th>
                <th className="text-right">预留</th>
                <th className="text-right">可用</th>
                <th>调整</th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 ? (
                <EmptyRow colSpan={6}>没有匹配的变体。</EmptyRow>
              ) : (
                visible.map((row) => (
                  <InventoryRow
                    key={row.variant.id}
                    productName={row.productName}
                    productStatus={row.productStatus}
                    variant={row.variant}
                  />
                ))
              )}
            </tbody>
          </table>
        )}
      </Panel>
    </>
  );
}

function InventoryRow({
  variant,
  productName,
  productStatus,
}: {
  variant: AdminVariant;
  productName: string;
  productStatus: string;
}) {
  const queryClient = useQueryClient();
  const [delta, setDelta] = useState("1");
  const [note, setNote] = useState("");

  const stock = useQuery({
    queryKey: ["inventory", variant.id],
    queryFn: () => getInventory(variant.id),
  });

  const adjust = useMutation({
    mutationFn: () => adjustInventory(variant.id, Number(delta), note || undefined),
    onSuccess: (updated) => {
      setNote("");
      // Seed the row from the authoritative response, then let the catalogue
      // list re-read so the product table shows the same number.
      queryClient.setQueryData(["inventory", variant.id], updated);
      void queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });

  const available = stock.data?.available ?? variant.available;
  const step = Number(delta);
  const valid = Number.isInteger(step) && step !== 0;

  return (
    <tr>
      <td>
        <p className="text-slate-100">{productName}</p>
        <StatusChip label={productStatus} tone="border-ink-line text-slate-400" />
      </td>
      <td className="font-mono text-xs text-slate-400">{variant.sku}</td>
      <td className="text-right text-slate-200">{stock.data?.quantity ?? "—"}</td>
      <td className="text-right text-slate-400">{stock.data?.reserved ?? "—"}</td>
      <td className={`text-right font-semibold ${available <= LOW_STOCK ? "text-red-300" : "text-slate-100"}`}>
        {available}
      </td>
      <td>
        <div className="flex items-center gap-2">
          <input
            className="field w-20 py-1 text-xs"
            onChange={(event) => setDelta(event.target.value)}
            type="number"
            value={delta}
          />
          <input
            className="field w-36 py-1 text-xs"
            onChange={(event) => setNote(event.target.value)}
            placeholder="备注（可选）"
            value={note}
          />
          <button
            className="btn-ghost py-1 text-xs"
            disabled={!valid || adjust.isPending}
            onClick={() => adjust.mutate()}
            type="button"
          >
            {adjust.isPending ? "提交中…" : "应用"}
          </button>
        </div>
        {adjust.error ? (
          <p className="mt-1 text-[10px] text-red-400">
            {adjust.error instanceof Error ? adjust.error.message : "调整失败"}
          </p>
        ) : null}
      </td>
    </tr>
  );
}
