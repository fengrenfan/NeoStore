/**
 * Server-safe shared constants.
 *
 * Deliberately free of the `"use client"` directive. The buyer-facing cookie name
 * is read both in the browser (`@/lib/session`, a client module) and on the
 * server (middleware, server components). Importing a value exported from a
 * `"use client"` module into server-side code makes that value evaluate to
 * `undefined` at runtime in Next.js — which silently broke region resolution in
 * the middleware. Keeping it here means every consumer gets the real string.
 */
export const REGION_COOKIE = "neostore_region";
