import type { Metadata } from "next";

import { LOCALES } from "./locales";

export function siteUrl(): string {
  return process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
}

/**
 * `hreflang` alternates for one logical page.
 *
 * Every language points at the *same* path under a different prefix, which is
 * exactly what the middleware serves, so the alternates never 404. English is
 * also advertised as `x-default` — the fallback a search engine uses when no
 * language matches.
 */
export function alternateLanguages(path: string): Record<string, string> {
  const suffix = path === "/" ? "" : path;
  const languages: Record<string, string> = {};

  for (const code of LOCALES) {
    languages[code] = `${siteUrl()}/${code}${suffix}`;
  }
  languages["x-default"] = `${siteUrl()}/${
    LOCALES.includes("en") ? "en" : (LOCALES[0] ?? "en")
  }${suffix}`;

  return languages;
}

export function alternatesFor(locale: string, path: string): Metadata["alternates"] {
  const suffix = path === "/" ? "" : path;
  return {
    canonical: `${siteUrl()}/${locale}${suffix}`,
    languages: alternateLanguages(path),
  };
}

/** Prefix a path with a locale for internal links and metadata. */
export function localizedPath(locale: string, path: string): string {
  return `/${locale}${path === "/" ? "" : path}`;
}
