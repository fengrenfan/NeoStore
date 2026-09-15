"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ApiError, getCart, getCartTotals, removeCartLine, updateCartLine } from "@/lib/api";
import { notifyCartChanged } from "@/lib/cart-store";
import { formatMoney } from "@/lib/format";
import { readCartToken } from "@/lib/session";
import type { Cart, CartTotals } from "@/lib/types";

export interface CartLabels {
  cartTitle: string;
  cartEmpty: string;
  continueShopping: string;
  subtotal: string;
  shipping: string;
  free: string;
  tax: string;
  total: string;
  toCheckout: string;
  remove: string;
  quantity: string;
  loading: string;
  somethingWentWrong: string;
  retry: string;
}

type Phase = "loading" | "empty" | "ready" | "error";

/**
 * The cart itself.
 *
 * Anonymous carts are addressed by an opaque token held in `localStorage`, so
 * this has to be a client component — the server never sees the token and
 * therefore cannot render the lines. Totals are always read from the API rather
 * than recomputed here: the cart's region was fixed when it was created, and
 * only the backend knows which tax rate applies to it.
 */
export function CartView({ locale, labels }: { locale: string; labels: CartLabels }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [cart, setCart] = useState<Cart | null>(null);
  const [totals, setTotals] = useState<CartTotals | null>(null);
  const [busyLine, setBusyLine] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = readCartToken();
    if (!token) {
      setPhase("empty");
      return;
    }
    try {
      const [nextCart, nextTotals] = await Promise.all([getCart(token), getCartTotals(token)]);
      setCart(nextCart);
      setTotals(nextTotals);
      setPhase(nextCart.lines.length === 0 ? "empty" : "ready");
    } catch (error) {
      // A cart that no longer exists on the server is indistinguishable from an
      // empty one from the shopper's point of view; anything else is a real
      // failure worth surfacing.
      if (error instanceof ApiError && error.status === 404) {
        setPhase("empty");
        return;
      }
      setMessage(error instanceof ApiError ? error.message : labels.somethingWentWrong);
      setPhase("error");
    }
  }, [labels.somethingWentWrong]);

  useEffect(() => {
    void load();
  }, [load]);

  async function mutate(lineId: string, action: () => Promise<Cart>) {
    setBusyLine(lineId);
    setMessage(null);
    try {
      const nextCart = await action();
      setCart(nextCart);
      notifyCartChanged();
      if (nextCart.lines.length === 0) {
        setTotals(null);
        setPhase("empty");
      } else {
        setTotals(await getCartTotals(nextCart.token));
      }
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : labels.somethingWentWrong);
    } finally {
      setBusyLine(null);
    }
  }

  if (phase === "loading") {
    return <p className="text-sm text-slate-400">{labels.loading}</p>;
  }

  if (phase === "error") {
    return (
      <div className="surface space-y-3 p-6">
        <p className="text-sm text-red-400">{message ?? labels.somethingWentWrong}</p>
        <button className="btn-ghost" onClick={() => void load()} type="button">
          {labels.retry}
        </button>
      </div>
    );
  }

  if (phase === "empty" || !cart) {
    return (
      <div className="surface space-y-4 p-8 text-center">
        <p className="text-sm text-slate-400">{labels.cartEmpty}</p>
        <Link className="btn-primary" href={`/${locale}/products`}>
          {labels.continueShopping}
        </Link>
      </div>
    );
  }

  const currency = totals?.currency ?? cart.currency_code;

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
      <ul className="space-y-3">
        {cart.lines.map((line) => (
          <li className="surface flex flex-wrap items-center gap-4 p-4" key={line.id}>
            <div className="min-w-40 flex-1">
              <p className="font-mono text-xs text-slate-400">{line.variant_id.slice(0, 8)}</p>
              <p className="text-sm text-slate-100">
                {formatMoney(line.unit_price, line.currency_code, locale)}
              </p>
            </div>

            <label className="flex items-center gap-2">
              <span className="sr-only">{labels.quantity}</span>
              <input
                className="field w-20"
                disabled={busyLine === line.id}
                min={1}
                onChange={(event) => {
                  const quantity = Math.max(1, Number(event.target.value) || 1);
                  void mutate(line.id, () => updateCartLine(cart.token, line.id, quantity));
                }}
                type="number"
                value={line.quantity}
              />
            </label>

            <p className="w-28 text-right text-sm font-semibold text-neon-cyan">
              {formatMoney(
                String(Number(line.unit_price) * line.quantity),
                line.currency_code,
                locale,
              )}
            </p>

            <button
              className="text-xs text-slate-400 underline transition hover:text-red-400"
              disabled={busyLine === line.id}
              onClick={() => void mutate(line.id, () => removeCartLine(cart.token, line.id))}
              type="button"
            >
              {labels.remove}
            </button>
          </li>
        ))}
      </ul>

      <aside className="surface h-fit space-y-3 p-5">
        <dl className="space-y-2 text-sm">
          <Row
            label={labels.subtotal}
            value={totals ? formatMoney(totals.subtotal, currency, locale) : "—"}
          />
          <Row
            label={labels.shipping}
            value={
              totals
                ? Number(totals.shipping_fee) === 0
                  ? labels.free
                  : formatMoney(totals.shipping_fee, currency, locale)
                : "—"
            }
          />
          <Row
            label={labels.tax}
            value={totals ? formatMoney(totals.tax, currency, locale) : "—"}
          />
          <div className="border-t border-ink-line pt-3">
            <Row
              emphasis
              label={labels.total}
              value={totals ? formatMoney(totals.total, currency, locale) : "—"}
            />
          </div>
        </dl>

        <Link className="btn-primary w-full" href={`/${locale}/checkout`}>
          {labels.toCheckout}
        </Link>

        {message ? <p className="text-xs text-red-400">{message}</p> : null}
      </aside>
    </div>
  );
}

function Row({
  label,
  value,
  emphasis = false,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className={emphasis ? "text-slate-200" : "text-slate-400"}>{label}</dt>
      <dd className={emphasis ? "font-semibold text-white" : "text-slate-200"}>{value}</dd>
    </div>
  );
}
