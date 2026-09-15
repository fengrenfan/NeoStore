import { NextResponse, type NextRequest } from "next/server";

import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  matchLocale,
  negotiateLocale,
} from "@/lib/locales";

/**
 * Puts every request inside a locale prefix.
 *
 * Resolution order: the path prefix wins, then the remembered cookie, then
 * `Accept-Language`, then the default. A tag we recognise but do not render
 * exactly (e.g. `en-GB` when only `en` exists) is canonicalised with a redirect
 * so the address bar never shows a locale that is not real.
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

    const response = NextResponse.next();
    response.cookies.set(LOCALE_COOKIE, matched, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
    });
    return response;
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
