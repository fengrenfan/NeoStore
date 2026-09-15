"use client";

import { useEffect } from "react";

/**
 * Route-level error boundary.
 *
 * The usual cause here is the API being unreachable, which is worth saying out
 * loud rather than showing Next's generic overlay.
 */
export default function LocaleError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("storefront route error", error);
  }, [error]);

  return (
    <div className="surface mx-auto max-w-lg space-y-4 p-10 text-center">
      <p className="text-sm font-semibold text-red-400">Something went wrong</p>
      <p className="text-xs text-slate-400">
        The storefront could not reach the NeoStore API. Check that the backend is running.
      </p>
      {error.digest ? (
        <p className="font-mono text-[11px] text-slate-600">{error.digest}</p>
      ) : null}
      <button className="btn-ghost" onClick={reset} type="button">
        Retry
      </button>
    </div>
  );
}
