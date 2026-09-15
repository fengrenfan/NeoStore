import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Header } from "@/components/Header";
import { getLocales, getRegions, tolerantDuringBuild } from "@/lib/api";
import { DEFAULT_LOCALE, LOCALES, isSupportedLocale } from "@/lib/locales";
import { currentRegion } from "@/lib/server";
import { copy } from "@/lib/strings";

import "../globals.css";

/**
 * This is the application's root layout — it lives inside `[locale]` so the
 * document's `lang` attribute is always correct, which is what the i18n routing
 * pattern in Next's own docs does. There is deliberately no `app/layout.tsx`.
 */

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export const metadata: Metadata = {
  title: { default: "NeoStore", template: "%s · NeoStore" },
  description:
    "NeoStore — a cross-border DTC storefront with multi-language and multi-currency pricing.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  // The file lives in `public/`, so nothing links it and the browser falls back
  // to requesting /favicon.ico — which 404s on every page load.
  icons: { icon: "/favicon.svg" },
};

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isSupportedLocale(locale)) notFound();

  // Regions drive the currency switcher; locales give the switcher the API's own
  // display names. Both are cached by the fetch layer, and both fall back to the
  // configured list while prerendering (see `tolerantDuringBuild`).
  const [availableLocales, regions] = await Promise.all([
    tolerantDuringBuild(
      getLocales(),
      LOCALES.map((code) => ({
        code,
        name: code,
        is_default: code === DEFAULT_LOCALE,
      })),
    ),
    tolerantDuringBuild(getRegions(), []),
  ]);
  const region = await currentRegion(regions);
  const t = copy(locale);

  const localeCodes = LOCALES.filter((code) =>
    availableLocales.some((row) => row.code === code),
  );
  const localeLabels: Record<string, string> = { ...t.localeLabels };
  for (const row of availableLocales) {
    localeLabels[row.code] = row.name;
  }

  return (
    <html lang={locale}>
      <body className="flex min-h-screen flex-col bg-ink text-slate-100">
        <Header
          currentRegion={region}
          labels={{
            home: t.navHome,
            products: t.navProducts,
            cart: t.navCart,
            localeLabels,
          }}
          locale={locale}
          locales={localeCodes}
          regions={regions}
        />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10">{children}</main>
        <footer className="border-t border-ink-line py-8 text-center text-xs text-slate-500">
          {t.footerNote}
        </footer>
      </body>
    </html>
  );
}
