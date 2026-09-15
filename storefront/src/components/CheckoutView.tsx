"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, checkout, getCart, getCartTotals } from "@/lib/api";
import { notifyCartChanged } from "@/lib/cart-store";
import { formatMoney } from "@/lib/format";
import {
  clearCartToken,
  newIdempotencyKey,
  readCartToken,
  writeRegion,
} from "@/lib/session";
import type { CartTotals, ShippingAddress } from "@/lib/types";

export interface CheckoutLabels {
  checkoutTitle: string;
  email: string;
  fullName: string;
  addressLine1: string;
  addressLine2: string;
  city: string;
  postalCode: string;
  country: string;
  subtotal: string;
  shipping: string;
  free: string;
  tax: string;
  total: string;
  placeOrder: string;
  placingOrder: string;
  paymentNote: string;
  loading: string;
  somethingWentWrong: string;
  backToShop: string;
}

const EMPTY: ShippingAddress = {
  name: "",
  line1: "",
  line2: "",
  city: "",
  postal_code: "",
  country: "",
};

/**
 * Checkout.
 *
 * The cart token lives in `localStorage`, so the form is client-side. Two
 * details carry real weight:
 *
 * 1. The idempotency key is minted once and kept for the whole attempt. If the
 *    submit is retried — double click, flaky network — the API returns the same
 *    order instead of reserving stock twice.
 * 2. The cart token is cleared only *after* the order number comes back, so a
 *    failed submit still has a cart to retry with.
 */
export function CheckoutView({
  locale,
  defaultCountry,
  labels,
}: {
  locale: string;
  defaultCountry: string;
  labels: CheckoutLabels;
}) {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [totals, setTotals] = useState<CartTotals | null>(null);
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState<ShippingAddress>({ ...EMPTY, country: defaultCountry });
  const [idempotencyKey] = useState(newIdempotencyKey);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const stored = readCartToken();
    setToken(stored);
    if (!stored) return;
    getCartTotals(stored)
      .then(setTotals)
      .catch(() => setTotals(null));
  }, []);

  function update<K extends keyof ShippingAddress>(key: K, value: ShippingAddress[K]) {
    setAddress((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;

    setSubmitting(true);
    setMessage(null);
    try {
      const order = await checkout({
        cartToken: token,
        email,
        shippingAddress: address,
        idempotencyKey,
      });
      clearCartToken();
      notifyCartChanged();
      router.push(`/${locale}/orders/${order.number}`);
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : labels.somethingWentWrong);
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="surface space-y-4 p-8 text-center">
        <p className="text-sm text-slate-400">{labels.somethingWentWrong}</p>
        <Link className="btn-ghost" href={`/${locale}/products`}>
          {labels.backToShop}
        </Link>
      </div>
    );
  }

  return (
    <form className="grid gap-8 lg:grid-cols-[1fr_320px]" onSubmit={submit}>
      <div className="space-y-4">
        <Field label={labels.email}>
          <input
            autoComplete="email"
            className="field"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
        </Field>

        <Field label={labels.fullName}>
          <input
            autoComplete="name"
            className="field"
            onChange={(event) => update("name", event.target.value)}
            required
            value={address.name}
          />
        </Field>

        <Field label={labels.addressLine1}>
          <input
            autoComplete="address-line1"
            className="field"
            onChange={(event) => update("line1", event.target.value)}
            required
            value={address.line1}
          />
        </Field>

        <Field label={labels.addressLine2}>
          <input
            autoComplete="address-line2"
            className="field"
            onChange={(event) => update("line2", event.target.value)}
            value={address.line2 ?? ""}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label={labels.city}>
            <input
              autoComplete="address-level2"
              className="field"
              onChange={(event) => update("city", event.target.value)}
              required
              value={address.city}
            />
          </Field>
          <Field label={labels.postalCode}>
            <input
              autoComplete="postal-code"
              className="field"
              onChange={(event) => update("postal_code", event.target.value)}
              value={address.postal_code ?? ""}
            />
          </Field>
          <Field label={labels.country}>
            <input
              autoComplete="country"
              className="field"
              onChange={(event) => {
                update("country", event.target.value);
                // Keep the region cookie in step with what was typed: an order
                // delivered to the US should keep pricing the shop in USD.
                if (event.target.value.length === 2) {
                  writeRegion(event.target.value.toLowerCase());
                }
              }}
              required
              value={address.country}
            />
          </Field>
        </div>

        <p className="text-xs leading-relaxed text-slate-500">{labels.paymentNote}</p>
      </div>

      <aside className="surface h-fit space-y-3 p-5">
        <dl className="space-y-2 text-sm">
          <SummaryRow
            label={labels.subtotal}
            value={totals ? formatMoney(totals.subtotal, totals.currency, locale) : "—"}
          />
          <SummaryRow
            label={labels.shipping}
            value={
              totals
                ? Number(totals.shipping_fee) === 0
                  ? labels.free
                  : formatMoney(totals.shipping_fee, totals.currency, locale)
                : "—"
            }
          />
          <SummaryRow
            label={labels.tax}
            value={totals ? formatMoney(totals.tax, totals.currency, locale) : "—"}
          />
          <div className="border-t border-ink-line pt-3">
            <SummaryRow
              emphasis
              label={labels.total}
              value={totals ? formatMoney(totals.total, totals.currency, locale) : "—"}
            />
          </div>
        </dl>

        <button className="btn-primary w-full" disabled={submitting} type="submit">
          {submitting ? labels.placingOrder : labels.placeOrder}
        </button>

        {message ? <p className="text-xs text-red-400">{message}</p> : null}
      </aside>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}

function SummaryRow({
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
