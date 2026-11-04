import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#faf8f5",
        card: "#ffffff",
        ink: { DEFAULT: "#1f2430", soft: "#4b5367", mute: "#6b7389" },
        line: "#e8e3db",
        brand: { DEFAULT: "#3b5bdb", soft: "#edf2ff", dark: "#2b44a8" },
        teal: { DEFAULT: "#0ca678", soft: "#e6fcf5", ink: "#087f5b" },
        amber: { DEFAULT: "#f08c00", soft: "#fff4e0", ink: "#8a5200" },
        calm: { DEFAULT: "#7048e8", soft: "#f3f0ff", ink: "#5f3dc4" },
        sky: { DEFAULT: "#1c7ed6", soft: "#e7f5ff" },
        danger: { DEFAULT: "#c92a2a", soft: "#fff0f0" },
        tint: { weak: "#eef2ff", support: "#e6fcf5", parent: "#fff4e0", results: "#f3f0ff", student: "#e7f5ff", add: "#fff9db", home: "#edf2ff", plain: "#f4f1ec" },
      },
      fontFamily: {
        sans: ["Inter Variable", "Noto Sans Devanagari Variable", "system-ui", "sans-serif"],
      },
      fontSize: { xs: ["0.8125rem", "1.2rem"], sm: ["0.9375rem", "1.4rem"] },
      borderRadius: { xl: "14px", "2xl": "20px" },
      boxShadow: { soft: "0 1px 2px rgba(31,36,48,.05), 0 8px 24px -10px rgba(31,36,48,.14)", lift: "0 2px 4px rgba(31,36,48,.06), 0 14px 32px -12px rgba(59,91,219,.28)" },
      keyframes: { pageIn: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } }, pop: { "0%": { transform: "scale(.96)", opacity: "0" }, "100%": { transform: "none", opacity: "1" } } },
      animation: { page: "pageIn .28s ease-out both", pop: "pop .2s ease-out both" },
    },
  },
  plugins: [],
};
export default config;
