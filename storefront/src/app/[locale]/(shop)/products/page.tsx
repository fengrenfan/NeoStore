import type { Metadata } from "next";

import { ProductCard } from "@/components/ProductCard";
import { getProducts, tolerantDuringBuild } from "@/lib/api";
import { alternatesFor } from "@/lib/seo";
import { regionContext } from "@/lib/server";
import { copy } from "@/lib/strings";

/** Per-request for the same reason as the homepage: prices follow the region. */
export const dynamic = "force-dynamic";

const PAGE_SIZE = 24;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = copy(locale);
  return {
    title: t.productsTitle,
    alternates: alternatesFor(locale, "/products"),
  };
}

export default async function ProductsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = copy(locale);
  const { region } = await regionContext();

  const page = await tolerantDuringBuild(
    getProducts({
      locale,
      region: region?.code,
      limit: PAGE_SIZE,
    }),
    { items: [], total: 0 },
  );

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold">
          <span className="neon-text">{t.productsTitle}</span>
        </h1>
        <p className="text-xs text-slate-400">
          {t.productsCount(page.items.length, page.total)}
          {region ? (
            <>
              {" · "}
              <span className="pill">
                {region.name} · {region.currency_code}
              </span>
            </>
          ) : null}
        </p>
      </header>

      {page.items.length === 0 ? (
        <p className="surface p-6 text-sm text-slate-400">{t.productsEmpty}</p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {page.items.map((product) => (
            <ProductCard key={product.id} locale={locale} product={product} />
          ))}
        </div>
      )}
    </div>
  );
}
