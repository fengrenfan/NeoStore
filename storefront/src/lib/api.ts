/**
 * The only place that talks to the NeoStore API.
 *
 * Two base URLs, because the storefront runs in two places: server components
 * render inside the compose network (where the API is `http://backend:8000`)
 * while the browser needs a publicly reachable one. Set both in `.env`.
 */

import type {
  Cart,
  CartTotals,
  Locale,
  Order,
  ProductDetail,
  ProductListPage,
  Region,
  ShippingAddress,
} from "./types";

export const API_PREFIX = "/api/v1";

/** How long catalog reads are cached. Cart and order reads are never cached. */
export const CATALOG_REVALIDATE_SECONDS = 60;

/**
 * `next build` prerenders the static routes, which would otherwise require a
 * reachable API — and in the Docker build the API container is not up yet.
 *
 * So during the build phase only, an unreachable API degrades to a fallback and
 * the real data arrives on the first revalidation. At runtime the failure is
 * left alone: silently showing an empty catalog would look like "no products"
 * instead of an outage, and the route error boundary handles it better.
 */
const IS_BUILD = process.env.NEXT_PHASE === "phase-production-build";

export function tolerantDuringBuild<T>(promise: Promise<T>, fallback: T): Promise<T> {
  if (!IS_BUILD) return promise;
  return promise.catch((error: unknown) => {
    if (error instanceof ApiError && error.code === "NETWORK_ERROR") {
      console.warn(`[build] API unreachable, using fallback: ${error.message}`);
      return fallback;
    }
    throw error;
  });
}

const FALLBACK_BASE_URL = "http://127.0.0.1:8000";

function baseUrl(): string {
  if (typeof window === "undefined") {
    return (
      process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? FALLBACK_BASE_URL
    );
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? FALLBACK_BASE_URL;
}

/** The API's unified error envelope, surfaced as a typed throwable. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type Json = Record<string, unknown>;

async function readBody(response: Response): Promise<Json | null> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as Json;
  } catch {
    return null;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Extra request headers, e.g. ``Idempotency-Key`` on checkout. */
  headers?: Record<string, string>;
  /** Server-side ISR window. Omit for anything per-visitor (cart, orders). */
  revalidate?: number;
  /** Set for per-visitor reads so Next never serves them from the cache. */
  cache?: RequestCache;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers: {
      accept: "application/json",
      ...(options.body === undefined ? {} : { "content-type": "application/json" }),
      ...options.headers,
    },
  };

  if (options.body !== undefined) {
    init.body = JSON.stringify(options.body);
  }
  if (options.cache) {
    init.cache = options.cache;
  }
  if (options.revalidate !== undefined) {
    // Server components opt into ISR; the browser ignores this key entirely.
    (init as RequestInit & { next?: { revalidate: number } }).next = {
      revalidate: options.revalidate,
    };
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl()}${API_PREFIX}${path}`, init);
  } catch (cause) {
    throw new ApiError(
      503,
      "NETWORK_ERROR",
      `could not reach the NeoStore API at ${baseUrl()}`,
      { cause: String(cause) },
    );
  }

  if (!response.ok) {
    const parsed = await readBody(response);
    const error = parsed?.error as
      | { code?: string; message?: string; details?: Record<string, unknown> }
      | undefined;
    throw new ApiError(
      response.status,
      error?.code ?? "HTTP_ERROR",
      error?.message ?? `request failed with ${response.status}`,
      error?.details ?? {},
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
}

// ------------------------------------------------------------------ reference

export function getLocales(): Promise<Locale[]> {
  return request<Locale[]>("/store/locales", { revalidate: CATALOG_REVALIDATE_SECONDS });
}

export function getRegions(): Promise<Region[]> {
  return request<Region[]>("/store/regions", { revalidate: CATALOG_REVALIDATE_SECONDS });
}

// ------------------------------------------------------------------- catalog

export async function getProducts(params: {
  locale: string;
  region?: string;
  limit?: number;
  offset?: number;
  category?: string;
}): Promise<ProductListPage> {
  const path = `/store/products${query({
    locale: params.locale,
    region: params.region,
    limit: params.limit,
    offset: params.offset,
    category: params.category,
  })}`;

  const response = await raw(path, { revalidate: CATALOG_REVALIDATE_SECONDS });
  const items = (await response.json()) as ProductListPage["items"];
  const total = Number(response.headers.get("x-total-count") ?? items.length);
  return { items, total };
}

export function getProduct(
  slug: string,
  params: { locale: string; region?: string },
): Promise<ProductDetail> {
  return request<ProductDetail>(
    `/store/products/${encodeURIComponent(slug)}${query({
      locale: params.locale,
      region: params.region,
    })}`,
    { revalidate: CATALOG_REVALIDATE_SECONDS },
  );
}

// ---------------------------------------------------------------------- cart

export function createCart(region?: string): Promise<Cart> {
  return request<Cart>("/store/carts", {
    method: "POST",
    body: region ? { region } : {},
    cache: "no-store",
  });
}

export function getCart(token: string): Promise<Cart> {
  return request<Cart>(`/store/carts/${encodeURIComponent(token)}`, {
    cache: "no-store",
  });
}

/**
 * Totals use the cart's *own* region, not the region currently being browsed —
 * the backend guarantees a cart is only ever taxed once.
 */
export function getCartTotals(token: string): Promise<CartTotals> {
  return request<CartTotals>(`/store/carts/${encodeURIComponent(token)}/totals`, {
    cache: "no-store",
  });
}

export function addCartLine(token: string, variantId: string, quantity: number): Promise<Cart> {
  return request<Cart>(`/store/carts/${encodeURIComponent(token)}/lines`, {
    method: "POST",
    body: { variant_id: variantId, quantity },
    cache: "no-store",
  });
}

export function updateCartLine(
  token: string,
  lineId: string,
  quantity: number,
): Promise<Cart> {
  return request<Cart>(`/store/carts/${encodeURIComponent(token)}/lines/${lineId}`, {
    method: "PATCH",
    body: { quantity },
    cache: "no-store",
  });
}

export function removeCartLine(token: string, lineId: string): Promise<Cart> {
  return request<Cart>(`/store/carts/${encodeURIComponent(token)}/lines/${lineId}`, {
    method: "DELETE",
    cache: "no-store",
  });
}

// --------------------------------------------------------------------- order

/**
 * Place the order.
 *
 * The idempotency key is required, not optional: a double-clicked "Pay" or a
 * retried request after a flaky connection must return the *same* order rather
 * than reserving stock twice. Callers keep the key stable for one checkout
 * attempt.
 */
export function checkout(params: {
  cartToken: string;
  email: string;
  shippingAddress: ShippingAddress;
  idempotencyKey: string;
  paymentProvider?: string;
}): Promise<Order> {
  return request<Order>("/store/checkout", {
    method: "POST",
    headers: { "idempotency-key": params.idempotencyKey },
    body: {
      cart_token: params.cartToken,
      email: params.email,
      shipping_address: params.shippingAddress,
      payment_provider: params.paymentProvider ?? "mock",
    },
    cache: "no-store",
  });
}

export function getOrder(number: string): Promise<Order> {
  return request<Order>(`/store/orders/${encodeURIComponent(number)}`, {
    cache: "no-store",
  });
}

/**
 * Stands in for the gateway callback that confirms payment.
 *
 * The backend only serves this while `ENABLE_MOCK_PAYMENTS` is on, and 404s
 * otherwise — so a failure here in production is expected, not a bug.
 */
export function payOrder(number: string): Promise<Order> {
  return request<Order>(`/store/orders/${encodeURIComponent(number)}/pay`, {
    method: "POST",
    cache: "no-store",
  });
}

// ----------------------------------------------------------------- internals

/** Like `request` but hands back the raw response, for header-only metadata. */
async function raw(urlPath: string, options: RequestOptions = {}): Promise<Response> {
  const init: RequestInit = { method: "GET", headers: { accept: "application/json" } };
  if (options.cache) init.cache = options.cache;
  if (options.revalidate !== undefined) {
    (init as RequestInit & { next?: { revalidate: number } }).next = {
      revalidate: options.revalidate,
    };
  }

  const response = await fetch(`${baseUrl()}${API_PREFIX}${urlPath}`, init);
  if (!response.ok) {
    const parsed = await readBody(response);
    const error = parsed?.error as { code?: string; message?: string } | undefined;
    throw new ApiError(
      response.status,
      error?.code ?? "HTTP_ERROR",
      error?.message ?? `request failed with ${response.status}`,
    );
  }
  return response;
}
