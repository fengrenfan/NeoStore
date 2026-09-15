"use client";

/**
 * Browser-side session state: the anonymous cart token and the chosen region.
 *
 * The API also sets an HttpOnly cart cookie, but the storefront keeps the token
 * in `localStorage` as well so the cart survives being served from a different
 * host (Caddy in front of the API, for instance) and so the checkout call can
 * pass it explicitly. The token is opaque and unguessable; holding it is what
 * grants access to the cart, which is exactly how anonymous carts work.
 */

export const CART_STORAGE_KEY = "neostore.cart_token";

/** Must match `region_cookie_name` in the backend settings. */
export const REGION_COOKIE = "neostore_region";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function readCartToken(): string | null {
  if (!isBrowser()) return null;
  try {
    return window.localStorage.getItem(CART_STORAGE_KEY);
  } catch {
    // Private browsing can throw on storage access; a lost cart is acceptable.
    return null;
  }
}

export function writeCartToken(token: string): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(CART_STORAGE_KEY, token);
  } catch {
    /* ignore */
  }
}

export function clearCartToken(): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.removeItem(CART_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function readRegion(): string | null {
  if (!isBrowser()) return null;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${REGION_COOKIE}=`));
  return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : null;
}

export function writeRegion(code: string): void {
  if (!isBrowser()) return;
  const year = 60 * 60 * 24 * 365;
  document.cookie = `${REGION_COOKIE}=${encodeURIComponent(code)}; path=/; max-age=${year}; samesite=lax`;
}

/** A fresh, collision-resistant key for one checkout attempt. */
export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `ck_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}
