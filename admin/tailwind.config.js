/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0B0B12",
          raised: "#14141F",
          line: "#23233A",
        },
        neon: {
          violet: "#7C5CFF",
          cyan: "#22D3EE",
        },
        positive: "#34D399",
        warning: "#FBBF24",
      },
      backgroundImage: {
        "neon-gradient": "linear-gradient(120deg, #7C5CFF 0%, #22D3EE 100%)",
      },
    },
  },
  plugins: [],
};
