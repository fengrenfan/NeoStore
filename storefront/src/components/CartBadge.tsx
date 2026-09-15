"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { getCart } from "@/lib/api";
import { cartLineCount, onCartChanged } from "@/lib/cart-store";
import { readCartToken } from "@/lib/session";

/**
 * Shows how many units are in the cart.
 *
 * The cart lives in the browser (anonymous token in `localStorage`), so this
 * cannot be a server component. It re-reads on mount and whenever anything
 * dispatches `CART_EVENT`, which keeps it in step with the cart page without
 * pulling in a state library.
 */
export function CartBadge({ locale, label }: { locale: string; label: string }) {
  const [count, setCount] = useState<number | null>(null);

  const refresh = useCallback(() => {
    const token = readCartToken();
    if (!token) {
      setCount(0);
      return;
    }
    getCart(token)
      .then((cart) => setCount(cartLineCount(cart.lines)))
      .catch(() => setCount(0));
  }, []);

  useEffect(() => {
    refresh();
    return onCartChanged(refresh);
  }, [refresh]);

  return (
    <Link
      className="relative inline-flex h-9 items-center gap-2 rounded-xl border border-ink-line px-3 text-sm text-slate-200 transition hover:border-neon-violet/60 hover:text-white"
      href={`/${locale}/cart`}
    >
      <span aria-hidden>🛍</span>
      <span>{label}</span>
      {count !== null && count > 0 ? (
        <span
          aria-label={`${label}: ${count}`}
          className="absolute -right-2 -top-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-neon-gradient px-1 text-[11px] font-bold text-ink"
        >
          {count}
        </span>
      ) : null}
    </Link>
  );
}
