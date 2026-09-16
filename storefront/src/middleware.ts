import { NextResponse, type NextRequest } from "next/server";

import { REGION_COOKIE } from "@/lib/constants";
import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  matchLocale,
  negotiateLocale,
} from "@/lib/locales";

/**
 * Puts every request inside a locale prefix, and keeps the active region in the
 * URL as `?region=` — the canonical, always-fresh source of truth for pricing.
 *
 * A region chosen in the browser is written as the `neostore_region` cookie and
 * then pushed onto the URL by the switcher. This middleware makes the two agree:
 *   - a `?region=` in the URL wins and is mirrored back into the cookie;
 *   - otherwise a `neostore_region` cookie is redirected into the URL (a 307, not a
 *     silent rewrite) so server components still see the region on links that do
 *     not carry the `?region=` param. A rewrite is served from the static
 *     prerender here and would silently drop the region, reverting to default.
 *
 * Why the URL and not the cookie alone: a cookie written client-side with
 * `document.cookie` is not reliably visible to Next's `cookies()` on the server
 * in this deployment, so the URL is what the server actually trusts.
 *
 * Locale resolution order: path prefix wins, then remembered cookie, then
 * `Accept-Language`, then the default. A tag we recognise but do not render
 * exactly (e.g. `en-GB` when only `en` exists) is canonicalised with a redirect
 * so the address bar never shows a locale that is not real.
 *
 * Cookie names must come from a module WITHOUT `"use client"`. `REGION_COOKIE`
 * used to be imported from `@/lib/session`, which carries that directive;
 * importing a *value* from a client module into server-side code makes it
 * `undefined` at runtime, so `request.cookies.get(undefined)` never matched and
 * the cookie-to-URL redirect silently did nothing. The name now lives in
 * `@/lib/constants`.
 *
 * Debugging note, so nobody repeats it: `request.cookies.get()` works fine in
 * this runtime. An earlier round blamed it and hand-parsed the raw `Cookie`
 * header instead, but the culprit was always the `undefined` cookie name above —
 * with the name fixed, the framework accessor behaves correctly.
 */
export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;
  const segments = pathname.split("/").filter(Boolean);
  const first = segments[0];
  const matched = matchLocale(first);

  if (matched && first) {
    if (matched !== first) {
      const url = request.nextUrl.clone();
      url.pathname = `/${[matched, ...segments.slice(1)].join("/")}`;
      return NextResponse.redirect(url);
    }

    // Locale prefix is valid — now reconcile region.
    const url = request.nextUrl.clone();
    const regionParam = url.searchParams.get("region");
    const regionCookie = request.cookies.get(REGION_COOKIE)?.value;

    if (regionParam) {
      // URL is canonical: mirror it into the cookie for continuity, and forward
      // it to the server components via a request header. `searchParams` is not
      // reliably delivered to server components in this standalone build, so the
      // header (set by the middleware from the URL) is what the page actually
      // reads for the *current* request — the cookie only helps later navigations.
      const requestHeaders = new Headers(request.headers);
      requestHeaders.set("x-neostore-region", regionParam);
      const response = NextResponse.next({ request: { headers: requestHeaders } });
      response.cookies.set(REGION_COOKIE, regionParam, {
        path: "/",
        maxAge: 60 * 60 * 24 * 365,
        sameSite: "lax",
      });
      return response;
    }

    if (regionCookie) {
      // No `?region=` on this link, but we remember the choice. Redirect (not
      // rewrite) so the region lands in the URL and the page renders it
      // per-request. In this deployment a `rewrite` to the same pathname is
      // served from the static prerender and silently drops the injected query,
      // so the currency would revert to default. Build the target from the full
      // request URL so the query param is preserved (a bare `nextUrl.clone()`
      // redirect was dropping it, causing a loop).
      const target = new URL(request.url);
      target.searchParams.set("region", regionCookie);
      return NextResponse.redirect(target);
    }

    return NextResponse.next();
  }

  const locale =
    matchLocale(request.cookies.get(LOCALE_COOKIE)?.value) ??
    negotiateLocale(request.headers.get("accept-language")) ??
    DEFAULT_LOCALE;

  const url = request.nextUrl.clone();
  url.pathname = `/${[locale, ...segments].join("/")}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Everything except Next internals and the SEO files that must stay at the
  // root (`/robots.txt`, `/sitemap.xml`).
  matcher: ["/((?!_next|api|favicon.ico|robots.txt|sitemap.xml|.*\\.[^/]+$).*)"],
};
