import type { MetadataRoute } from "next";

import { getProducts } from "@/lib/api";
import { LOCALES } from "@/lib/locales";
import { alternateLanguages, siteUrl } from "@/lib/seo";

export const revalidate = 3600;

/**
 * One entry per logical page, with every locale advertised as an alternate.
 *
 * The catalog call is wrapped because a sitemap that 500s is worse than one
 * that lists only the static pages.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteUrl();

  const products = await getProducts({ locale: LOCALES[0] ?? "en", limit: 100 }).catch(() => ({
    items: [],
    total: 0,
  }));

  const staticPaths = ["/", "/products", "/cart", "/checkout"];
  const productPaths = products.items.map((product) => `/products/${product.slug}`);
  const paths = [...staticPaths, ...productPaths];

  const entries: MetadataRoute.Sitemap = [];
  for (const path of paths) {
    const languages = alternateLanguages(path);
    for (const locale of LOCALES) {
      entries.push({
        url: `${base}/${locale}${path === "/" ? "" : path}`,
        changeFrequency: path === "/" ? "daily" : "weekly",
        priority: path === "/" ? 1 : 0.7,
        alternates: { languages },
      });
    }
  }

  return entries;
}
