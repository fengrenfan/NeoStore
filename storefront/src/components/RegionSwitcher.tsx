"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import type { Region } from "@/lib/types";
import { writeRegion } from "@/lib/session";

/**
 * Switching region re-renders the current page server-side with new pricing,
 * so the change goes through the cookie plus `router.refresh()` rather than any
 * client-side conversion — the backend stays the only thing that prices.
 */
export function RegionSwitcher({
  regions,
  current,
}: {
  regions: Region[];
  current: Region | undefined;
}) {
  const router = useRouter();
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
          startTransition(() => {
            router.refresh();
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
