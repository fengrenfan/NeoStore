/**
 * Response shapes of the admin API.
 *
 * Money crosses the wire as a string (the API serialises `Decimal` that way) and
 * is only parsed for display. Nothing in this app does arithmetic on it.
 */

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AdminProfile {
  email: string;
  role: string;
}

export interface LocaleRead {
  code: string;
  name: string;
  is_default: boolean;
}

export interface CurrencyRead {
  code: string;
  name: string;
  symbol: string;
  decimal_places: number;
  is_active: boolean;
}

export interface RegionDetail {
  code: string;
  name: string;
  currency_code: string;
  tax_rate: string;
  is_default: boolean;
  locales: string[];
  payment_methods: string[];
}

export interface ExchangeRateRead {
  base_code: string;
  quote_code: string;
  rate: string;
  source: string;
  fetched_at: string;
}

export interface AdminTranslation {
  locale: string;
  name: string;
  slug: string;
  description: string | null;
  seo_title: string | null;
  seo_description: string | null;
}

export interface AdminVariant {
  id: string;
  sku: string;
  position: number;
  prices: Record<string, string>;
  available: number;
}

export interface AdminMedia {
  url: string;
  alt: string | null;
  position: number;
  is_primary: boolean;
}

export interface AdminProduct {
  id: string;
  status: string;
  product_type: string;
  base_price: string;
  base_currency: string;
  position: number;
  translations: AdminTranslation[];
  variants: AdminVariant[];
  media: AdminMedia[];
}

export interface AdminProductListPage {
  items: AdminProduct[];
  total: number;
  limit: number;
  offset: number;
}

export interface OrderLine {
  variant_id: string | null;
  product_name: string;
  variant_label: string | null;
  sku: string;
  unit_price: string;
  quantity: number;
  line_total: string;
  currency_code: string;
}

export interface OrderEvent {
  from_status: string | null;
  to_status: string;
  note: string | null;
  created_at: string;
}

export interface Order {
  id: string;
  number: string;
  status: string;
  region_code: string;
  currency_code: string;
  email: string;
  shipping_address: Record<string, string>;
  subtotal: string;
  shipping_fee: string;
  tax: string;
  total: string;
  lines: OrderLine[];
  events: OrderEvent[];
}

export interface OrderListPage {
  items: Order[];
  total: number;
  limit: number;
  offset: number;
}

export interface InventoryRead {
  variant_id: string;
  quantity: number;
  reserved: number;
  available: number;
}

/** Payload accepted by `POST /admin/products`. */
export interface ProductWrite {
  status: string;
  base_price: string;
  base_currency: string;
  translations: Record<string, Record<string, string | null>>;
  variants: {
    sku: string;
    position?: number;
    prices?: Record<string, string>;
  }[];
}
