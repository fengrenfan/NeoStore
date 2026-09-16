import Link from "next/link";

import { ProductCard } from "@/components/ProductCard";
import { getProducts, tolerantDuringBuild } from "@/lib/api";
import { regionContext, regionFromSearchParams } from "@/lib/server";
import { copy } from "@/lib/strings";

/**
 * Rendered per request: the region cookie decides which currency the prices are
 * in, so a single cached render would show one visitor's currency to everyone.
 * The catalog fetches inside keep their own 60s cache, so this does not mean a
 * database round trip per visit.
 */
export const dynamic = "force-dynamic";

const FEATURED_LIMIT = 6;

export default async function HomePage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { locale } = await params;
  const sp = await searchParams;
  const requestedRegion = Array.isArray(sp.region) ? sp.region[0] : sp.region;
  const t = copy(locale);
  const { region } = await regionContext(requestedRegion);

  // Prerendering has no API to talk to; at runtime a failed catalog call is left
  // to surface rather than rendering an empty shop that looks like "no stock".
  const products = await tolerantDuringBuild(
    getProducts({
      locale,
      region: region?.code,
      limit: FEATURED_LIMIT,
    }),
    { items: [], total: 0 },
  );

  return (
    <div className="space-y-12">
      <section className="surface relative overflow-hidden px-6 py-14 sm:px-10">
        <div className="pointer-events-none absolute inset-0 bg-neon-glow" aria-hidden />
        <div className="relative max-w-2xl space-y-5">
          <p className="pill">{t.tagline}</p>
          <h1 className="text-3xl font-bold leading-tight sm:text-4xl">
            <span className="neon-text">{t.heroTitle}</span>
          </h1>
          <p className="text-sm leading-relaxed text-slate-300">{t.heroSubtitle}</p>
          <Link className="btn-primary" href={`/${locale}/products`}>
            {t.heroCta}
          </Link>
        </div>
      </section>

      <section className="space-y-5">
        <h2 className="text-lg font-semibold text-slate-100">{t.featuredTitle}</h2>
        {products.items.length === 0 ? (
          <p className="text-sm text-slate-400">{t.productsEmpty}</p>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {products.items.map((product) => (
              <ProductCard key={product.id} locale={locale} product={product} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
