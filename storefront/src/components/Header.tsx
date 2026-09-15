"use client";

import { usePathname } from "next/navigation";

import { CartBadge } from "./CartBadge";
import { LocaleSwitcher } from "./LocaleSwitcher";
import { RegionSwitcher } from "./RegionSwitcher";
import type { Region } from "@/lib/types";

interface NavLabels {
  home: string;
  products: string;
  cart: string;
  localeLabels: Record<string, string>;
}

/**
 * The header is a client component so the locale switcher can read the current
 * pathname. Everything it needs about the visitor (locale, region) is passed in
 * from the server layout, so it renders without a loading state.
 */
export function Header({
  locale,
  locales,
  currentRegion,
  regions,
  labels,
}: {
  locale: string;
  locales: string[];
  currentRegion: Region | undefined;
  regions: Region[];
  labels: NavLabels;
}) {
  const pathname = usePathname() ?? `/${locale}`;

  const links = [
    { href: `/${locale}`, label: labels.home },
    { href: `/${locale}/products`, label: labels.products },
  ];

  return (
    <header className="sticky top-0 z-20 border-b border-ink-line bg-ink/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-4 px-4 py-3">
        <a className="text-lg font-bold tracking-tight neon-text" href={`/${locale}`}>
          NeoStore
        </a>

        <nav className="hidden gap-4 text-sm text-slate-300 sm:flex">
          {links.map((link) => (
            <a
              key={link.href}
              className="transition hover:text-white"
              href={link.href}
              data-active={pathname === link.href ? "true" : undefined}
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <RegionSwitcher current={currentRegion} regions={regions} />
          <LocaleSwitcher
            labels={labels.localeLabels}
            locale={locale}
            locales={locales}
            pathname={pathname}
          />
          <CartBadge label={labels.cart} locale={locale} />
        </div>
      </div>
    </header>
  );
}
