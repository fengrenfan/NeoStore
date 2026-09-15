import type { Config } from "tailwindcss";

/**
 * The palette is fixed by the design spec: a near-black base with a single
 * violet-to-cyan accent gradient. No other primary colours.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Named `ink` rather than `base`: a colour key called `base` would
        // collide with Tailwind's `text-base` font-size utility.
        ink: {
          DEFAULT: "#0B0B12",
          raised: "#12121C",
          line: "#22222F",
        },
        neon: {
          violet: "#7C5CFF",
          cyan: "#22D3EE",
        },
        positive: "#34D399",
      },
      backgroundImage: {
        "neon-gradient": "linear-gradient(90deg, #7C5CFF 0%, #22D3EE 100%)",
        "neon-glow":
          "radial-gradient(60% 60% at 50% 0%, rgba(124,92,255,0.28) 0%, rgba(11,11,18,0) 70%)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        neon: "0 0 0 1px rgba(124,92,255,0.35), 0 12px 40px -12px rgba(34,211,238,0.45)",
      },
    },
  },
  plugins: [],
};

export default config;
