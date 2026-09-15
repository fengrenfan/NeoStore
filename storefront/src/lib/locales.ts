/** Localisation primitives shared by middleware and components. */

/**
 * Locales the storefront renders. Kept in an env var rather than hardcoded
 * because adding a language is a *data* change on the backend, not a code
 * change — but middleware runs on the edge and cannot ask the database on every
 * request, so the storefront's list has to be declared. Keep it in sync with the
 * `locale` table (see `docs/RUNBOOK.md`).
 */
export const LOCALES: string[] = (process.env.NEXT_PUBLIC_LOCALES ?? "zh-CN,en,ja")
  .split(",")
  .map((code) => code.trim())
  .filter(Boolean);

export const DEFAULT_LOCALE: string = process.env.NEXT_PUBLIC_DEFAULT_LOCALE ?? "zh-CN";

/** Remembers the visitor's choice so `/` lands in the right language next time. */
export const LOCALE_COOKIE = "neostore_locale";

export function isSupportedLocale(value: string | undefined | null): value is string {
  return typeof value === "string" && LOCALES.includes(value);
}

/**
 * Best match for a path prefix, or `null` when nothing matches.
 *
 * The exact-hit test goes through `LOCALES.includes` rather than the
 * `isSupportedLocale` predicate: narrowing a value that is already `string`
 * with `value is string` leaves the negative branch as `never`.
 */
export function matchLocale(value: string | null | undefined): string | null {
  if (!value) return null;
  const candidate: string = value.trim();
  if (LOCALES.includes(candidate)) return candidate;

  // "en-GB" should land on "en".
  const base = candidate.split("-")[0];
  if (!base) return null;
  return LOCALES.find((code) => code.split("-")[0] === base) ?? null;
}

/**
 * Walk an `Accept-Language` header and take the first locale we render.
 * Deliberately ignores `q=` weights: honouring declaration order is what most
 * users expect and it keeps the matcher readable.
 */
export function negotiateLocale(header: string | null | undefined): string {
  if (!header) return DEFAULT_LOCALE;
  for (const part of header.split(",")) {
    const tag = part.split(";")[0]?.trim();
    if (!tag || tag === "*") continue;
    const match = matchLocale(tag);
    if (match) return match;
  }
  return DEFAULT_LOCALE;
}

/** Prefix an app-relative path with a locale, e.g. `/products` -> `/en/products`. */
export function localePath(locale: string, path: string): string {
  const suffix = path === "/" ? "" : path.startsWith("/") ? path : `/${path}`;
  return `/${locale}${suffix}`;
}
