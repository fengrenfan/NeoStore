import { cookies, headers } from "next/headers";

import { getRegions, tolerantDuringBuild } from "./api";
import type { Region } from "./types";
import { REGION_COOKIE } from "./constants";

/**
 * Safe extraction of the requested region from `searchParams`.
 *
 * In this standalone Next.js 15.1.6 build the `searchParams` prop arrives
 * `undefined` at runtime (even with `force-dynamic`), so reading `sp.region`
 * directly throws `TypeError: Cannot read properties of undefined`. This helper
 * defends against that and normalises the string|string[] shape.
 */
export function regionFromSearchParams(
  sp: Record<string, string | string[] | undefined> | undefined | null,
): string | null {
  if (!sp) return null;
  const value = sp.region;
  if (!value) return null;
  return Array.isArray(value) ? (value[0] ?? null) : value;
}

/**
 * Server-side region resolution.
 *
 * Canonical order for the *current* request:
 *   1. `x-neostore-region` request header — set by middleware from the URL's
 *      `?region=` (or from the remembered cookie, which the middleware redirects
 *      into the URL). This is the reliable per-request source: `searchParams` is
 *      not reliably delivered to server components in this standalone build, and
 *      a client-written cookie is not reliably visible to `cookies()` on soft
 *      navigations. The header is set by the server (middleware) on every hop,
 *      so it is always fresh for the request that is actually rendering.
 *   2. `?region=` query param (passed in as `requested`) — kept as a fallback for
 *      the rare case where middleware did not run but the param is present.
 *   3. `neostore_region` cookie — cross-navigation continuity (best effort).
 *   4. default / first region.
 */
export async function currentRegion(
  regions: Region[],
  requested?: string | null,
): Promise<Region | undefined> {
  if (regions.length === 0) return undefined;

  const headerRegion = (await headers()).get("x-neostore-region");
  if (headerRegion) {
    const match = regions.find((region) => region.code === headerRegion);
    if (match) return match;
  }

  if (requested) {
    const match = regions.find((region) => region.code === requested);
    if (match) return match;
  }

  const fromCookie = (await cookies()).get(REGION_COOKIE)?.value;
  if (fromCookie) {
    const match = regions.find((region) => region.code === fromCookie);
    if (match) return match;
  }

  return regions.find((region) => region.is_default) ?? regions[0];
}

/**
 * Regions plus the one this visitor is on.
 *
 * Reading `headers()`/`cookies()` opts the route into dynamic rendering, which
 * is correct here: prices differ per region and must not be shared between
 * visitors. The API responses underneath are still cached for
 * `CATALOG_REVALIDATE_SECONDS`, so a dynamic render does not mean a database hit.
 *
 * During a build there is no API, so the list falls back to empty and the call
 * returns early instead of failing the prerender. Routes that depend on this
 * are marked `force-dynamic`, so that fallback is never what a visitor sees.
 */
export async function regionContext(requested?: string | null): Promise<{
  regions: Region[];
  region: Region | undefined;
}> {
  const regions = await tolerantDuringBuild(getRegions(), []);
  return { regions, region: await currentRegion(regions, requested) };
}
