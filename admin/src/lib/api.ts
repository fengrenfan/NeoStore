/**
 * The only place that talks to the API.
 *
 * Every request carries the bearer token when there is one, and the console is
 * mounted under `/admin/` while the API lives at `/api/` — so paths here are
 * absolute from the domain root and Caddy routes them. In development Vite's
 * proxy does the same job (see `vite.config.ts`).
 */

import type {
  AdminProduct,
  AdminProductListPage,
  AdminProfile,
  CurrencyRead,
  ExchangeRateRead,
  InventoryRead,
  LocaleRead,
  Order,
  OrderListPage,
  ProductWrite,
  RegionDetail,
  TokenResponse,
} from "./types";

const API_PREFIX = "/api/v1/admin";
const TOKEN_KEY = "neostore.admin_token";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function readToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function writeToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* private browsing can refuse storage; the session simply won't persist */
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

interface Options {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | undefined>;
}

async function request<T>(path: string, options: Options = {}): Promise<T> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const suffix = search.toString() ? `?${search}` : "";

  const token = readToken();
  const headers: Record<string, string> = { accept: "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers["content-type"] = "application/json";

  const response = await fetch(`${API_PREFIX}${path}${suffix}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const parsed = text ? (JSON.parse(text) as Record<string, unknown>) : null;

  if (!response.ok) {
    const error = parsed?.error as
      | { code?: string; message?: string; details?: Record<string, unknown> }
      | undefined;
    // A rejected token is worth acting on immediately rather than showing an
    // error the operator cannot do anything about.
    if (response.status === 401) clearToken();
    throw new ApiError(
      response.status,
      error?.code ?? "HTTP_ERROR",
      error?.message ?? `request failed with ${response.status}`,
      error?.details ?? {},
    );
  }

  return parsed as T;
}

// ------------------------------------------------------------------- auth

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

export function me(): Promise<AdminProfile> {
  return request<AdminProfile>("/auth/me");
}

// --------------------------------------------------------------- products

export function listProducts(params: { limit?: number; offset?: number } = {}) {
  return request<AdminProductListPage>("/products", { query: params });
}

export function getProduct(id: string): Promise<AdminProduct> {
  return request<AdminProduct>(`/products/${id}`);
}

export function createProduct(payload: ProductWrite): Promise<AdminProduct> {
  return request<AdminProduct>("/products", { method: "POST", body: payload });
}

export function updateProduct(
  id: string,
  payload: Partial<ProductWrite>,
): Promise<AdminProduct> {
  return request<AdminProduct>(`/products/${id}`, { method: "PATCH", body: payload });
}

export function deleteProduct(id: string): Promise<void> {
  return request<void>(`/products/${id}`, { method: "DELETE" });
}

export function setVariantPrice(
  productId: string,
  variantId: string,
  currencyCode: string,
  amount: string,
): Promise<AdminProduct> {
  return request<AdminProduct>(`/products/${productId}/variants/${variantId}/price`, {
    method: "PUT",
    body: { currency_code: currencyCode, amount },
  });
}

// ----------------------------------------------------------------- orders

export function listOrders(params: { status?: string; limit?: number; offset?: number } = {}) {
  return request<OrderListPage>("/orders", { query: params });
}

export function getOrder(ref: string): Promise<Order> {
  return request<Order>(`/orders/${ref}`);
}

export function orderTransitions(ref: string): Promise<string[]> {
  return request<string[]>(`/orders/${ref}/transitions`);
}

export function updateOrderStatus(
  ref: string,
  status: string,
  note?: string,
): Promise<Order> {
  return request<Order>(`/orders/${ref}/status`, {
    method: "PATCH",
    body: { status, note },
  });
}

// -------------------------------------------------------------- inventory

export function getInventory(variantId: string): Promise<InventoryRead> {
  return request<InventoryRead>(`/inventory/${variantId}`);
}

export function adjustInventory(
  variantId: string,
  delta: number,
  note?: string,
): Promise<InventoryRead> {
  return request<InventoryRead>(`/inventory/${variantId}/adjust`, {
    method: "POST",
    body: { delta, reason: "manual", note },
  });
}

// --------------------------------------------------------------- settings

export function listLocales(): Promise<LocaleRead[]> {
  return request<LocaleRead[]>("/settings/locales");
}

export function listCurrencies(): Promise<CurrencyRead[]> {
  return request<CurrencyRead[]>("/settings/currencies");
}

export function listRegions(): Promise<RegionDetail[]> {
  return request<RegionDetail[]>("/settings/regions");
}

export function listExchangeRates(base = "USD"): Promise<ExchangeRateRead[]> {
  return request<ExchangeRateRead[]>("/settings/exchange-rates", { query: { base } });
}

export function refreshExchangeRates(base = "USD"): Promise<{ updated: number; base: string }> {
  return request<{ updated: number; base: string }>("/settings/exchange-rates/refresh", {
    method: "POST",
    query: { base },
  });
}

/**
 * Pin a pair to a hand-entered rate.
 *
 * The storefront prefers an explicit per-currency price and only converts as a
 * fallback — this is the rate that fallback uses when the provider has no
 * usable quote.
 */
export function overrideExchangeRate(
  baseCode: string,
  quoteCode: string,
  rate: string,
): Promise<ExchangeRateRead> {
  return request<ExchangeRateRead>("/settings/exchange-rates", {
    method: "PUT",
    body: { base_code: baseCode, quote_code: quoteCode, rate, source: "manual" },
  });
}
