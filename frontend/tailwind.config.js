/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "Noto Sans Devanagari", "sans-serif"],
        display: ["Sora", "Noto Sans Devanagari", "sans-serif"],
      },
      colors: {
        ink: "#172033",
        muted: "#687386",
        line: "#e5e9f0",
        brand: { DEFAULT: "#176b52", dark: "#123d31", mid: "#1d5c4b", light: "#22956f" },
        amber: "#eaa72b",
        warn: "#d88900",
        danger: "#c93b3b",
        canvas: "#f5f7fb",
      },
      boxShadow: {
        card: "0 10px 30px rgba(18, 61, 49, 0.08)",
      },
    },
  },
  plugins: [],
};
