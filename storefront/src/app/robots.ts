import type { MetadataRoute } from "next";

import { siteUrl } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Carts and orders are per-visitor and order numbers are guessable
        // enough that they should never end up in an index.
        disallow: ["/api/", "/*/cart", "/*/checkout", "/*/orders/"],
      },
    ],
    sitemap: `${siteUrl()}/sitemap.xml`,
  };
}
