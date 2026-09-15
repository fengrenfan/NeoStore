"use client";

import Link from "next/link";
import { useState } from "react";

import { ApiError, addCartLine, createCart } from "@/lib/api";
import { notifyCartChanged } from "@/lib/cart-store";
import { formatMoney } from "@/lib/format";
import { readCartToken, readRegion, writeCartToken } from "@/lib/session";
import type { Variant } from "@/lib/types";

type Status = "idle" | "busy" | "added" | "error";

/**
 * Adds one variant to the cart.
 *
 * Creating the cart lazily on first add keeps the storefront from minting a
 * cart row for every visitor who only browses. The region stored on that cart
 * comes from the cookie set by the region switcher, so the cart is taxed the
 * same way the page was priced.
 *
 * Note the strings are passed in individually rather than as the whole copy
 * object: functions cannot cross the server/client boundary.
 */
export function AddToCartForm({
  locale,
  variants,
  currency,
  labels,
}: {
  locale: string;
  variants: Variant[];
  currency: string;
  labels: {
    addToCart: string;
    adding: string;
    added: string;
    viewCart: string;
    chooseVariant: string;
    inStockLabel: string;
    outOfStock: string;
    soldOut: string;
    sku: string;
    quantity: string;
    failed: string;
  };
}) {
  const firstAvailable = variants.find((variant) => variant.available > 0) ?? variants[0];
  const [variantId, setVariantId] = useState(firstAvailable?.id ?? "");
  const [quantity, setQuantity] = useState(1);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const selected = variants.find((variant) => variant.id === variantId);
  const soldOut = !selected || selected.available <= 0;

  async function addToCart() {
    if (!selected) return;
    setStatus("busy");
    setMessage(null);
    try {
      let token = readCartToken();
      if (!token) {
        const cart = await createCart(readRegion() ?? undefined);
        token = cart.token;
        writeCartToken(token);
      }
      await addCartLine(token, selected.id, quantity);
      notifyCartChanged();
      setStatus("added");
      setMessage(labels.added);
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof ApiError ? `${labels.failed} (${error.code})` : labels.failed,
      );
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <span className="field-label">{labels.chooseVariant}</span>
        <div className="flex flex-wrap gap-2">
          {variants.map((variant, index) => {
            const active = variant.id === variantId;
            const disabled = variant.available <= 0;
            return (
              <button
                aria-pressed={active}
                className={`rounded-xl border px-3 py-2 text-left text-xs transition ${
                  active
                    ? "border-neon-violet bg-neon-violet/10 text-white"
                    : "border-ink-line text-slate-300 hover:border-neon-violet/60"
                } ${disabled ? "opacity-50" : ""}`}
                disabled={disabled}
                key={variant.id}
                onClick={() => {
                  setVariantId(variant.id);
                  setStatus("idle");
                  setMessage(null);
                }}
                type="button"
              >
                <span className="block font-medium">
                  {variant.label ?? `${labels.sku} ${index + 1}`}
                </span>
                <span className="block text-[11px] text-slate-400">
                  {formatMoney(variant.price, currency, locale)}
                </span>
                <span className="block text-[11px] text-slate-500">
                  {variant.available > 0
                    ? `${labels.inStockLabel} ${variant.available}`
                    : labels.outOfStock}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="w-24">
          <span className="field-label">{labels.quantity}</span>
          <input
            className="field"
            min={1}
            max={Math.max(1, selected?.available ?? 1)}
            onChange={(event) => setQuantity(Math.max(1, Number(event.target.value) || 1))}
            type="number"
            value={quantity}
          />
        </label>

        <button
          className="btn-primary"
          disabled={soldOut || status === "busy"}
          onClick={addToCart}
          type="button"
        >
          {soldOut ? labels.soldOut : status === "busy" ? labels.adding : labels.addToCart}
        </button>

        {selected ? (
          <span className="pill">
            {labels.sku} {selected.sku}
          </span>
        ) : null}
      </div>

      {message ? (
        <p
          className={`text-sm ${status === "error" ? "text-red-400" : "text-positive"}`}
          role="status"
        >
          {message}
          {status === "added" ? (
            <>
              {" · "}
              <Link className="underline decoration-neon-cyan" href={`/${locale}/cart`}>
                {labels.viewCart}
              </Link>
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
