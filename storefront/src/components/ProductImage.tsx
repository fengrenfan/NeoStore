"use client";

import { useState } from "react";

/**
 * The seeded catalog points at a placeholder CDN, so images routinely fail to
 * load in a fresh install. Rather than showing a broken-image icon, fall back to
 * the brand gradient with the product's initial.
 */
export function ProductImage({
  src,
  alt,
  className = "",
}: {
  src: string | null;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div
        aria-label={alt}
        className={`flex items-center justify-center bg-gradient-to-br from-neon-violet/25 via-ink-raised to-neon-cyan/20 ${className}`}
        role="img"
      >
        <span className="text-3xl font-bold text-white/70">{alt.slice(0, 1)}</span>
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- remote host is operator-configured
    <img
      alt={alt}
      className={`object-cover ${className}`}
      loading="lazy"
      onError={() => setFailed(true)}
      src={src}
    />
  );
}
