import type { Metadata } from "next";

import { CartView } from "@/components/CartView";
import { copy } from "@/lib/strings";

export const metadata: Metadata = {
  title: "Cart",
  // A cart is per-visitor and worth nothing to a crawler.
  robots: { index: false, follow: false },
};

export default async function CartPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = copy(locale);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">
        <span className="neon-text">{t.cartTitle}</span>
      </h1>
      <CartView
        labels={{
          cartTitle: t.cartTitle,
          cartEmpty: t.cartEmpty,
          continueShopping: t.continueShopping,
          subtotal: t.subtotal,
          shipping: t.shipping,
          free: t.free,
          tax: t.tax,
          total: t.total,
          toCheckout: t.toCheckout,
          remove: t.remove,
          quantity: t.quantity,
          loading: t.loading,
          somethingWentWrong: t.somethingWentWrong,
          retry: t.retry,
        }}
        locale={locale}
      />
    </div>
  );
}
