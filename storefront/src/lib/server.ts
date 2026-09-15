import { cookies } from "next/headers";

import { getRegions, tolerantDuringBuild } from "./api";
import type { Region } from "./types";
import { REGION_COOKIE } from "./session";

/**
 * Server-side region resolution.
 *
 * Reads the same cookie the storefront writes, then validates it against the
 * regions the API actually serves. An unknown or stale code degrades to the
 * default region instead of erroring, matching how the backend negotiates it.
 */
export async function currentRegion(regions: Region[]): Promise<Region | undefined> {
  if (regions.length === 0) return undefined;

  const store = await cookies();
  const requested = store.get(REGION_COOKIE)?.value;

  if (requested) {
    const match = regions.find((region) => region.code === requested);
    if (match) return match;
  }

  return regions.find((region) => region.is_default) ?? regions[0];
}

/**
 * Regions plus the one this visitor is on.
 *
 * Reading a cookie opts the route into dynamic rendering, which is correct
 * here: prices differ per region and must not be shared between visitors. The
 * API responses underneath are still cached for `CATALOG_REVALIDATE_SECONDS`,
 * so a dynamic render does not mean a database hit.
 *
 * During a build there is no API, so the list falls back to empty and the call
 * returns early instead of failing the prerender. Routes that depend on this
 * are marked `force-dynamic`, so that fallback is never what a visitor sees.
 */
export async function regionContext(): Promise<{
  regions: Region[];
  region: Region | undefined;
}> {
  const regions = await tolerantDuringBuild(getRegions(), []);
  return { regions, region: await currentRegion(regions) };
}
