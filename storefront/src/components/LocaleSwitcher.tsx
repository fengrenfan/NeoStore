"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

/**
 * Switches language by swapping the locale prefix, keeping the rest of the path
 * intact — a visitor reading a product page stays on that product.
 *
 * The options come from the server (the intersection of what the storefront
 * renders and what the API can actually translate), so this never offers a
 * language that would silently fall back to the default.
 */
export function LocaleSwitcher({
  locale,
  locales,
  pathname,
  labels,
}: {
  locale: string;
  locales: string[];
  pathname: string;
  labels: Record<string, string>;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  if (locales.length < 2) return null;

  const rest = (() => {
    const segments = pathname.split("/").filter(Boolean);
    return segments.length > 0 ? `/${segments.slice(1).join("/")}` : "";
  })();

  return (
    <label className="flex items-center gap-1">
      <span className="sr-only">Language</span>
      <select
        aria-label="Language"
        className="rounded-lg border border-ink-line bg-ink px-2 py-1 text-xs text-slate-200"
        disabled={pending}
        onChange={(event) => {
          const next = event.target.value;
          startTransition(() => {
            router.push(`/${next}${rest}`);
          });
        }}
        value={locale}
      >
        {locales.map((code) => (
          <option key={code} value={code}>
            {labels[code] ?? code}
          </option>
        ))}
      </select>
    </label>
  );
}
