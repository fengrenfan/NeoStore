import type { Metadata } from "next";

import { CheckoutView } from "@/components/CheckoutView";
import { regionContext } from "@/lib/server";
import { copy } from "@/lib/strings";

export const metadata: Metadata = {
  title: "Checkout",
  robots: { index: false, follow: false },
};

/** The prefilled country comes from the region cookie, so this is per-visitor. */
export const dynamic = "force-dynamic";

export default async function CheckoutPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = copy(locale);
  const { region } = await regionContext();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">
        <span className="neon-text">{t.checkoutTitle}</span>
      </h1>
      <CheckoutView
        defaultCountry={region?.code.toUpperCase() ?? ""}
        labels={{
          checkoutTitle: t.checkoutTitle,
          email: t.email,
          fullName: t.fullName,
          addressLine1: t.addressLine1,
          addressLine2: t.addressLine2,
          city: t.city,
          postalCode: t.postalCode,
          country: t.country,
          subtotal: t.subtotal,
          shipping: t.shipping,
          free: t.free,
          tax: t.tax,
          total: t.total,
          placeOrder: t.placeOrder,
          placingOrder: t.placingOrder,
          paymentNote: t.paymentNote,
          loading: t.loading,
          somethingWentWrong: t.somethingWentWrong,
          backToShop: t.backToShop,
        }}
        locale={locale}
      />
    </div>
  );
}
