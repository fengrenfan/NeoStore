/**
 * Response shapes of the NeoStore API.
 *
 * Hand-written on purpose: they are small, and reading
 * `components["schemas"]["ProductCardRead"]` everywhere hurts more than it
 * helps. `npm run gen:types` regenerates the full OpenAPI payload into
 * `src/lib/api-types.ts` (gitignored) when you need to check the real contract.
 *
 * Money is always a *string* — the API serialises `Decimal` that way, and
 * parsing it into a `number` here would throw away the guarantee.
 */

export interface Locale {
  code: string;
  name: string;
  is_default: boolean;
}

export interface Region {
  code: string;
  name: string;
  currency_code: string;
  tax_rate: string;
  is_default: boolean;
  locales: string[];
  payment_methods: string[];
}

export interface Variant {
  id: string;
  sku: string;
  label: string | null;
  price: string;
  available: number;
}

export interface Media {
  url: string;
  alt: string | null;
}

export interface ProductCard {
  id: string;
  slug: string;
  name: string;
  price: string;
  currency: string;
  status: string;
  image: string | null;
}

export interface ProductDetail extends ProductCard {
  description: string | null;
  seo_title: string | null;
  seo_description: string | null;
  variants: Variant[];
  media: Media[];
}

export interface CartLine {
  id: string;
  variant_id: string;
  quantity: number;
  unit_price: string;
  currency_code: string;
}

export interface Cart {
  token: string;
  region_code: string;
  currency_code: string;
  status: string;
  lines: CartLine[];
}

export interface CartTotals {
  currency: string;
  subtotal: string;
  shipping_fee: string;
  tax: string;
  total: string;
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

export interface ShippingAddress {
  name: string;
  line1: string;
  line2?: string;
  city: string;
  postal_code?: string;
  country: string;
}

export interface ProductListPage {
  items: ProductCard[];
  total: number;
}
