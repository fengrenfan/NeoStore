import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AddToCartForm } from "@/components/AddToCartForm";
import { ProductImage } from "@/components/ProductImage";
import { ApiError, getProduct } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { alternatesFor, localizedPath, siteUrl } from "@/lib/seo";
import { regionContext, regionFromSearchParams } from "@/lib/server";
import { copy } from "@/lib/strings";
import type { ProductDetail } from "@/lib/types";

/** Per-request for the same reason as the homepage: prices follow the region. */
export const dynamic = "force-dynamic";

/**
 * Returns `null` when the product genuinely does not exist (so the page and the
 * metadata can both render a 404) and rethrows anything else — swallowing a 500
 * as "not found" would hide real outages.
 */
async function fetchProduct(
  slug: string,
  locale: string,
  requestedRegion?: string | null,
): Promise<ProductDetail | null> {
  const { region } = await regionContext(requestedRegion);
  try {
    return await getProduct(slug, { locale, region: region?.code });
  } catch (error) {
    if (error instanceof ApiError && error.code === "PRODUCT_NOT_FOUND") return null;
    throw error;
  }
}

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}): Promise<Metadata> {
  const { locale, slug } = await params;
  const sp = await searchParams;
  const requestedRegion = Array.isArray(sp.region) ? sp.region[0] : sp.region;
  const product = await fetchProduct(slug, locale, requestedRegion);
  if (!product) return { title: "404", robots: { index: false } };

  const description = product.seo_description ?? product.description ?? undefined;

  return {
    title: product.seo_title ?? product.name,
    description,
    alternates: alternatesFor(locale, `/products/${slug}`),
    openGraph: {
      title: product.seo_title ?? product.name,
      description,
      type: "website",
      url: `${siteUrl()}${localizedPath(locale, `/products/${slug}`)}`,
      images: product.media[0]?.url ? [product.media[0].url] : undefined,
    },
  };
}

export default async function ProductPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { locale, slug } = await params;
  const requestedRegion = regionFromSearchParams(await searchParams);
  const t = copy(locale);
  const product = await fetchProduct(slug, locale, requestedRegion);
  if (!product) notFound();

  const { region } = await regionContext(requestedRegion);
  const [hero, ...gallery] = product.media;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.description ?? undefined,
    sku: product.variants[0]?.sku,
    image: product.media.map((media) => media.url),
    offers: product.variants.map((variant) => ({
      "@type": "Offer",
      sku: variant.sku,
      price: variant.price,
      priceCurrency: product.currency,
      availability:
        variant.available > 0
          ? "https://schema.org/InStock"
          : "https://schema.org/OutOfStock",
    })),
  };

  return (
    <div className="space-y-8">
      <nav className="text-xs text-slate-500">
        <Link className="hover:text-slate-300" href={`/${locale}`}>
          {t.navHome}
        </Link>
        <span aria-hidden> / </span>
        <Link className="hover:text-slate-300" href={`/${locale}/products`}>
          {t.navProducts}
        </Link>
      </nav>

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="surface overflow-hidden">
            <ProductImage
              alt={product.name}
              className="aspect-square w-full"
              src={hero?.url ?? null}
            />
          </div>
          {gallery.length > 0 ? (
            <div className="grid grid-cols-4 gap-3">
              {gallery.map((media) => (
                <div className="surface overflow-hidden" key={media.url}>
                  <ProductImage
                    alt={media.alt ?? product.name}
                    className="aspect-square w-full"
                    src={media.url}
                  />
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="space-y-6">
          <div className="space-y-2">
            <h1 className="text-2xl font-bold text-slate-100">{product.name}</h1>
            <p className="text-xl font-semibold text-neon-cyan">
              {formatMoney(product.price, product.currency, locale)}
            </p>
            {region ? (
              <p className="text-xs text-slate-500">
                {region.name} · {region.currency_code}
              </p>
            ) : null}
          </div>

          <AddToCartForm
            currency={product.currency}
            labels={{
              addToCart: t.addToCart,
              adding: t.adding,
              added: t.added,
              viewCart: t.viewCart,
              chooseVariant: t.chooseVariant,
              inStockLabel: t.inStockLabel,
              outOfStock: t.outOfStock,
              soldOut: t.soldOut,
              sku: t.sku,
              quantity: t.quantity,
              failed: t.somethingWentWrong,
            }}
            locale={locale}
            variants={product.variants}
          />

          {product.description ? (
            <section className="space-y-2 border-t border-ink-line pt-6">
              <h2 className="text-sm font-semibold text-slate-200">{t.description}</h2>
              <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300">
                {product.description}
              </p>
            </section>
          ) : null}
        </div>
      </div>

      <script
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        type="application/ld+json"
      />
    </div>
  );
}
