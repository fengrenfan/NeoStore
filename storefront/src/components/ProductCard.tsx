import Link from "next/link";

import { formatMoney } from "@/lib/format";
import type { ProductCard as ProductCardData } from "@/lib/types";

import { ProductImage } from "./ProductImage";

/** Server component: no interactivity, so it stays out of the client bundle. */
export function ProductCard({
  product,
  locale,
}: {
  product: ProductCardData;
  locale: string;
}) {
  return (
    <Link
      className="surface group flex flex-col overflow-hidden transition hover:border-neon-violet/60 hover:shadow-neon"
      href={`/${locale}/products/${product.slug}`}
    >
      <ProductImage alt={product.name} className="aspect-[4/5] w-full" src={product.image} />
      <div className="flex flex-1 flex-col p-4">
        <h3 className="line-clamp-2 text-sm font-medium text-slate-100">{product.name}</h3>
        <p className="mt-auto pt-2 text-sm font-semibold text-neon-cyan">
          {formatMoney(product.price, product.currency, locale)}
        </p>
      </div>
    </Link>
  );
}
