"use client";

/** Fired whenever the cart's contents change, so badges/headers can refresh. */
export const CART_EVENT = "neostore:cart";

export function notifyCartChanged(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(CART_EVENT));
}

export function onCartChanged(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(CART_EVENT, listener);
  return () => window.removeEventListener(CART_EVENT, listener);
}

export function cartLineCount(lines: { quantity: number }[]): number {
  return lines.reduce((total, line) => total + line.quantity, 0);
}
