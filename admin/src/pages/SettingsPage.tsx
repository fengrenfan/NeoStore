import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { PageHeader } from "../components/Layout";
import { EmptyRow, ErrorNote, Panel, StatusChip } from "../components/Panel";
import {
  listCurrencies,
  listExchangeRates,
  listLocales,
  listRegions,
  overrideExchangeRate,
  refreshExchangeRates,
} from "../lib/api";
import { formatDateTime } from "../lib/format";

export function SettingsPage() {
  const locales = useQuery({ queryKey: ["locales"], queryFn: listLocales });
  const currencies = useQuery({ queryKey: ["currencies"], queryFn: listCurrencies });
  const regions = useQuery({ queryKey: ["regions"], queryFn: listRegions });

  return (
    <>
      <PageHeader
        description="语言、币种与地区是门店的一等公民：地区决定默认币种、税率与可用支付方式。"
        title="设置"
      />

      <div className="space-y-6">
        <ErrorNote error={locales.error ?? currencies.error ?? regions.error} />

        <RatePanel currencies={(currencies.data ?? []).map((row) => row.code)} />

        <Panel title={`语言（${locales.data?.length ?? 0}）`}>
          {locales.isLoading ? (
            <p className="text-sm text-slate-400">加载中…</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>默认</th>
                </tr>
              </thead>
              <tbody>
                {(locales.data ?? []).length === 0 ? (
                  <EmptyRow colSpan={3}>还没有可用语言。</EmptyRow>
                ) : (
                  (locales.data ?? []).map((locale) => (
                    <tr key={locale.code}>
                      <td className="font-mono text-xs text-neon-cyan">{locale.code}</td>
                      <td className="text-slate-100">{locale.name}</td>
                      <td>
                        {locale.is_default ? (
                          <StatusChip label="默认" tone="border-positive/40 text-positive" />
                        ) : (
                          <span className="text-xs text-slate-500">—</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title={`币种（${currencies.data?.length ?? 0}）`}>
          {currencies.isLoading ? (
            <p className="text-sm text-slate-400">加载中…</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>符号</th>
                  <th className="text-right">小数位</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {(currencies.data ?? []).length === 0 ? (
                  <EmptyRow colSpan={5}>还没有启用的币种。</EmptyRow>
                ) : (
                  (currencies.data ?? []).map((currency) => (
                    <tr key={currency.code}>
                      <td className="font-mono text-xs text-neon-cyan">{currency.code}</td>
                      <td className="text-slate-100">{currency.name}</td>
                      <td className="text-slate-300">{currency.symbol}</td>
                      <td className="text-right text-slate-300">{currency.decimal_places}</td>
                      <td>
                        <StatusChip
                          label={currency.is_active ? "启用" : "停用"}
                          tone={
                            currency.is_active
                              ? "border-positive/40 text-positive"
                              : "border-ink-line text-slate-400"
                          }
                        />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title={`地区（${regions.data?.length ?? 0}）`}>
          {regions.isLoading ? (
            <p className="text-sm text-slate-400">加载中…</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>币种</th>
                  <th className="text-right">税率</th>
                  <th>语言</th>
                  <th>支付方式</th>
                  <th>默认</th>
                </tr>
              </thead>
              <tbody>
                {(regions.data ?? []).length === 0 ? (
                  <EmptyRow colSpan={7}>还没有配置地区。</EmptyRow>
                ) : (
                  (regions.data ?? []).map((region) => (
                    <tr key={region.code}>
                      <td className="font-mono text-xs uppercase text-neon-cyan">{region.code}</td>
                      <td className="text-slate-100">{region.name}</td>
                      <td className="font-mono text-xs text-slate-300">{region.currency_code}</td>
                      <td className="text-right text-slate-300">{region.tax_rate}</td>
                      <td className="text-xs text-slate-400">
                        {region.locales.join(" · ") || "—"}
                      </td>
                      <td className="text-xs text-slate-400">
                        {region.payment_methods.join(" · ") || "—"}
                      </td>
                      <td>
                        {region.is_default ? (
                          <StatusChip label="默认" tone="border-positive/40 text-positive" />
                        ) : (
                          <span className="text-xs text-slate-500">—</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </>
  );
}

/**
 * Exchange rates are a fallback, not the primary price — so the panel is
 * optimistic about staleness and gives the operator a manual override for the
 * pairs a provider cannot cover.
 */
function RatePanel({ currencies }: { currencies: string[] }) {
  const queryClient = useQueryClient();
  const codes = currencies.length > 0 ? currencies : ["USD", "CNY", "JPY"];
  const [base, setBase] = useState(codes[0] ?? "USD");

  const [quote, setQuote] = useState("CNY");
  const [rate, setRate] = useState("");

  const rates = useQuery({
    queryKey: ["exchange-rates", base],
    queryFn: () => listExchangeRates(base),
  });

  const refresh = useMutation({
    mutationFn: () => refreshExchangeRates(base),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["exchange-rates"] }),
  });

  const override = useMutation({
    mutationFn: () => overrideExchangeRate(base, quote.toUpperCase(), rate),
    onSuccess: () => {
      setRate("");
      void queryClient.invalidateQueries({ queryKey: ["exchange-rates"] });
    },
  });

  return (
    <Panel
      actions={
        <div className="flex items-center gap-2">
          <select
            className="field w-24 py-1 text-xs"
            onChange={(event) => setBase(event.target.value)}
            value={base}
          >
            {codes.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
          <button
            className="btn-ghost py-1 text-xs"
            disabled={refresh.isPending}
            onClick={() => refresh.mutate()}
            type="button"
          >
            {refresh.isPending ? "刷新中…" : "拉取最新汇率"}
          </button>
        </div>
      }
      title={`汇率（基准 ${base}）`}
    >
      <ErrorNote error={rates.error ?? refresh.error ?? override.error} />

      {rates.isLoading ? (
        <p className="text-sm text-slate-400">加载中…</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>目标币种</th>
              <th className="text-right">汇率</th>
              <th>来源</th>
              <th>更新时间</th>
            </tr>
          </thead>
          <tbody>
            {(rates.data ?? []).length === 0 ? (
              <EmptyRow colSpan={4}>
                没有 {base} 的汇率记录。先拉取一次，或在下面手动填一条。
              </EmptyRow>
            ) : (
              (rates.data ?? []).map((row) => (
                <tr key={`${row.base_code}-${row.quote_code}`}>
                  <td className="font-mono text-xs text-neon-cyan">{row.quote_code}</td>
                  <td className="text-right font-semibold text-slate-100">{row.rate}</td>
                  <td className="text-xs text-slate-400">{row.source}</td>
                  <td className="text-xs text-slate-400">{formatDateTime(row.fetched_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}

      <div className="mt-5 flex flex-wrap items-end gap-3 border-t border-ink-line pt-5">
        <label className="w-28">
          <span className="field-label">基准</span>
          <p className="font-mono text-xs text-slate-300">{base}</p>
        </label>
        <label className="w-28">
          <span className="field-label">目标币种</span>
          <input
            className="field py-1 text-xs uppercase"
            onChange={(event) => setQuote(event.target.value)}
            value={quote}
          />
        </label>
        <label className="w-32">
          <span className="field-label">汇率</span>
          <input
            className="field py-1 text-xs"
            onChange={(event) => setRate(event.target.value)}
            placeholder="7.1800"
            value={rate}
          />
        </label>
        <button
          className="btn-primary py-1.5 text-xs"
          disabled={!rate || !quote || override.isPending}
          onClick={() => override.mutate()}
          type="button"
        >
          {override.isPending ? "保存中…" : "写入人工汇率"}
        </button>
        <p className="text-xs text-slate-500">
          人工写入会被标记为 manual，下次拉取时不会被覆盖掉。
        </p>
      </div>
    </Panel>
  );
}
