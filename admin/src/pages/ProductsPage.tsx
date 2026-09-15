import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { PageHeader } from "../components/Layout";
import { EmptyRow, ErrorNote, Panel, StatusChip } from "../components/Panel";
import {
  createProduct,
  listCurrencies,
  listLocales,
  listProducts,
  setVariantPrice,
  updateProduct,
} from "../lib/api";
import { formatMoney, productStatusLabel, productStatusTone } from "../lib/format";
import type { AdminProduct, ProductWrite } from "../lib/types";

const STATUSES = ["draft", "active", "archived"];

export function ProductsPage() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const products = useQuery({
    queryKey: ["products"],
    queryFn: () => listProducts({ limit: 100 }),
  });
  const locales = useQuery({ queryKey: ["locales"], queryFn: listLocales });
  const currencies = useQuery({ queryKey: ["currencies"], queryFn: listCurrencies });

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["products"] });
  }

  const setStatus = useMutation({
    mutationFn: (input: { id: string; status: string }) =>
      updateProduct(input.id, { status: input.status }),
    onSuccess: invalidate,
  });

  const rows = products.data?.items ?? [];

  return (
    <>
      <PageHeader
        actions={
          <button className="btn-primary" onClick={() => setCreating((open) => !open)} type="button">
            {creating ? "收起" : "新建商品"}
          </button>
        }
        description="每个语言的价格与文案独立维护；变体价格按币种显式定价。"
        title="商品"
      />

      <ErrorNote error={products.error ?? setStatus.error} />

      {creating ? (
        <div className="mb-6">
          <CreateProductForm
            currencies={(currencies.data ?? []).map((row) => row.code)}
            locales={(locales.data ?? []).map((row) => row.code)}
            onCreated={() => {
              invalidate();
              setCreating(false);
            }}
          />
        </div>
      ) : null}

      <Panel title={`全部商品（${products.data?.total ?? 0}）`}>
        {products.isLoading ? (
          <p className="text-sm text-slate-400">加载中…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>商品</th>
                <th>状态</th>
                <th>变体</th>
                <th>可用库存</th>
                <th>基础价</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <EmptyRow colSpan={6}>还没有商品。用上面的按钮新建一个。</EmptyRow>
              ) : (
                rows.map((product) => (
                  <ProductRow
                    expanded={expanded === product.id}
                    key={product.id}
                    onToggle={() =>
                      setExpanded((current) => (current === product.id ? null : product.id))
                    }
                    onStatusChange={(status) => setStatus.mutate({ id: product.id, status })}
                    onPriceSaved={invalidate}
                    product={product}
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

function ProductRow({
  product,
  expanded,
  onToggle,
  onStatusChange,
  onPriceSaved,
}: {
  product: AdminProduct;
  expanded: boolean;
  onToggle: () => void;
  onStatusChange: (status: string) => void;
  onPriceSaved: () => void;
}) {
  const primary = product.translations.find((row) => row.locale === "zh-CN") ?? product.translations[0];
  const available = product.variants.reduce((sum, variant) => sum + variant.available, 0);

  return (
    <>
      <tr>
        <td>
          <p className="text-slate-100">{primary?.name ?? "（未命名）"}</p>
          <p className="font-mono text-xs text-slate-500">
            {primary?.slug ?? product.id.slice(0, 8)}
          </p>
        </td>
        <td>
          <select
            className="field w-28 py-1 text-xs"
            onChange={(event) => onStatusChange(event.target.value)}
            value={product.status}
          >
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {productStatusLabel(status)}
              </option>
            ))}
          </select>
        </td>
        <td>
          <StatusChip label={`${product.variants.length}`} tone={productStatusTone(product.status)} />
        </td>
        <td className={available === 0 ? "text-red-300" : "text-slate-200"}>{available}</td>
        <td className="text-slate-200">
          {formatMoney(product.base_price, product.base_currency)}
        </td>
        <td className="text-right">
          <button className="btn-ghost py-1 text-xs" onClick={onToggle} type="button">
            {expanded ? "收起" : "变体与定价"}
          </button>
        </td>
      </tr>

      {expanded ? (
        <tr>
          <td className="bg-ink/60" colSpan={6}>
            <VariantPrices onSaved={onPriceSaved} product={product} />
          </td>
        </tr>
      ) : null}
    </>
  );
}

/**
 * Explicit per-currency pricing.
 *
 * The backend prefers an explicit price per currency and only falls back to a
 * converted one when nothing is set, so leaving a field blank is a legitimate
 * choice — not an oversight.
 */
function VariantPrices({ product, onSaved }: { product: AdminProduct; onSaved: () => void }) {
  const currencies = useQuery({ queryKey: ["currencies"], queryFn: listCurrencies });
  const codes = (currencies.data ?? []).map((row) => row.code);

  return (
    <div className="space-y-4 py-2">
      {product.variants.length === 0 ? (
        <p className="text-sm text-slate-500">这个商品还没有变体。</p>
      ) : (
        product.variants.map((variant) => (
          <div className="flex flex-wrap items-end gap-4" key={variant.id}>
            <div className="w-40">
              <span className="field-label">SKU</span>
              <p className="font-mono text-xs text-slate-300">{variant.sku}</p>
            </div>
            <div className="w-24">
              <span className="field-label">可用</span>
              <p className="text-xs text-slate-300">{variant.available}</p>
            </div>
            {codes.map((code) => (
              <PriceField
                code={code}
                key={code}
                onSaved={onSaved}
                productId={product.id}
                variantId={variant.id}
                value={variant.prices[code] ?? ""}
              />
            ))}
          </div>
        ))
      )}
    </div>
  );
}

function PriceField({
  productId,
  variantId,
  code,
  value,
  onSaved,
}: {
  productId: string;
  variantId: string;
  code: string;
  value: string;
  onSaved: () => void;
}) {
  const [amount, setAmount] = useState(value);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => setVariantPrice(productId, variantId, code, amount),
    onSuccess: () => {
      setError(null);
      onSaved();
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : "保存失败"),
  });

  return (
    <label className="w-28">
      <span className="field-label">{code}</span>
      <input
        className="field py-1 text-xs"
        onChange={(event) => setAmount(event.target.value)}
        onBlur={() => {
          if (amount && amount !== value) save.mutate();
        }}
        placeholder="跟随汇率"
        value={amount}
      />
      {error ? <span className="text-[10px] text-red-400">{error}</span> : null}
    </label>
  );
}

/**
 * Creating a product writes every locale's text at once, because the backend
 * treats translations as one atomic set. The tabs exist so it feels like
 * editing one page per language.
 */
function CreateProductForm({
  locales,
  currencies,
  onCreated,
}: {
  locales: string[];
  currencies: string[];
  onCreated: () => void;
}) {
  const activeLocales = locales.length > 0 ? locales : ["zh-CN", "en"];
  const [tab, setTab] = useState(activeLocales[0] ?? "zh-CN");
  const [status, setStatus] = useState("draft");
  const [currency, setCurrency] = useState(currencies[0] ?? "USD");
  const [basePrice, setBasePrice] = useState("0");
  const [skus, setSkus] = useState("");
  const [texts, setTexts] = useState<Record<string, Record<string, string>>>(
    () => Object.fromEntries(activeLocales.map((code) => [code, { name: "", slug: "" }])),
  );

  const create = useMutation({
    mutationFn: (payload: ProductWrite) => createProduct(payload),
    onSuccess: onCreated,
  });

  function update(field: "name" | "slug" | "description", next: string) {
    setTexts((current) => ({
      ...current,
      [tab]: { ...(current[tab] ?? {}), [field]: next },
    }));
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const translations: Record<string, Record<string, string | null>> = {};
    for (const code of activeLocales) {
      const row = texts[code] ?? {};
      if (!row.name || !row.slug) continue;
      translations[code] = {
        name: row.name,
        slug: row.slug,
        description: row.description ?? null,
      };
    }
    create.mutate({
      status,
      base_price: basePrice,
      base_currency: currency,
      translations,
      variants: skus
        .split(",")
        .map((sku) => sku.trim())
        .filter(Boolean)
        .map((sku, index) => ({ sku, position: index, prices: { [currency]: basePrice } })),
    });
  }

  return (
    <Panel title="新建商品">
      <form className="space-y-5" onSubmit={submit}>
        <div className="flex flex-wrap items-end gap-4">
          <label className="w-32">
            <span className="field-label">状态</span>
            <select
              className="field"
              onChange={(event) => setStatus(event.target.value)}
              value={status}
            >
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {productStatusLabel(value)}
                </option>
              ))}
            </select>
          </label>

          <label className="w-28">
            <span className="field-label">基础币种</span>
            <select
              className="field"
              onChange={(event) => setCurrency(event.target.value)}
              value={currency}
            >
              {(currencies.length > 0 ? currencies : ["USD", "CNY"]).map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
          </label>

          <label className="w-32">
            <span className="field-label">基础价</span>
            <input
              className="field"
              onChange={(event) => setBasePrice(event.target.value)}
              value={basePrice}
            />
          </label>

          <label className="min-w-56 flex-1">
            <span className="field-label">变体 SKU（逗号分隔）</span>
            <input
              className="field"
              onChange={(event) => setSkus(event.target.value)}
              placeholder="TEE-S, TEE-M"
              value={skus}
            />
          </label>
        </div>

        <div>
          <div className="flex gap-1 border-b border-ink-line">
            {activeLocales.map((code) => (
              <button
                className={`-mb-px border-b-2 px-3 py-2 text-xs transition ${
                  tab === code
                    ? "border-neon-violet text-white"
                    : "border-transparent text-slate-400 hover:text-slate-200"
                }`}
                key={code}
                onClick={() => setTab(code)}
                type="button"
              >
                {code}
                {texts[code]?.name ? " ✓" : ""}
              </button>
            ))}
          </div>

          <div className="grid gap-4 pt-4 sm:grid-cols-2">
            <label>
              <span className="field-label">名称（{tab}）</span>
              <input
                className="field"
                onChange={(event) => update("name", event.target.value)}
                value={texts[tab]?.name ?? ""}
              />
            </label>
            <label>
              <span className="field-label">Slug（{tab}）</span>
              <input
                className="field"
                onChange={(event) => update("slug", event.target.value)}
                value={texts[tab]?.slug ?? ""}
              />
            </label>
            <label className="sm:col-span-2">
              <span className="field-label">描述（{tab}）</span>
              <textarea
                className="field h-20"
                onChange={(event) => update("description", event.target.value)}
                value={texts[tab]?.description ?? ""}
              />
            </label>
          </div>
        </div>

        <ErrorNote error={create.error} />

        <div className="flex items-center gap-3">
          <button className="btn-primary" disabled={create.isPending} type="submit">
            {create.isPending ? "创建中…" : "创建商品"}
          </button>
          <p className="text-xs text-slate-500">
            只要某个语言填了名称和 slug，就会被写入；留空的语言直接跳过。
          </p>
        </div>
      </form>
    </Panel>
  );
}
