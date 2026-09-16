"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import type { Region } from "@/lib/types";
import { writeRegion } from "@/lib/session";

/**
 * Switching region re-renders the current page server-side with new pricing, so
 * the change goes through the URL (`?region=`) rather than any client-side
 * conversion — the backend stays the only thing that prices.
 *
 * The chosen region is pushed onto the URL (preserving any other query params,
 * e.g. a category filter) and mirrored into the `neostore_region` cookie by the
 * middleware, so the choice survives later navigations that omit the param. The
 * URL is the source of truth because a cookie written with `document.cookie`
 * is not reliably visible to the server in this deployment.
 */
export function RegionSwitcher({
  regions,
  current,
}: {
  regions: Region[];
  current: Region | undefined;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();

  if (regions.length === 0 || !current) return null;

  return (
    <label className="flex items-center gap-2 text-xs text-slate-400">
      <span className="sr-only">Region</span>
      <select
        aria-label="Region"
        className="rounded-lg border border-ink-line bg-ink px-2 py-1 text-xs text-slate-200"
        disabled={pending}
        value={current.code}
        onChange={(event) => {
          const code = event.target.value;
          writeRegion(code);
          const params = new URLSearchParams(searchParams.toString());
          params.set("region", code);
          startTransition(() => {
            router.push(`${pathname}?${params.toString()}`);
          });
        }}
      >
        {regions.map((region) => (
          <option key={region.code} value={region.code}>
            {region.name} · {region.currency_code}
          </option>
        ))}
      </select>
    </label>
  );
}
