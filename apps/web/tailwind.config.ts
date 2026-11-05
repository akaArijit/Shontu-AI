import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#12100e",
          900: "#171411",
          850: "#1a1714",
          800: "#1e1b17",
          750: "#24201c",
          700: "#2b2621",
          600: "#3a332c",
        },
        parchment: {
          50: "#fbf7f1",
          100: "#f1ebe2",
          200: "#ded4c6",
          300: "#c1b5a5",
          400: "#9c8f80",
          500: "#7b7065",
          600: "#655b51",
        },
        copper: {
          200: "#f0c7a8",
          300: "#dfa273",
          400: "#cf8452",
          500: "#b96a3a",
          600: "#9a542c",
          700: "#7a4022",
        },
        warm: {
          100: "#e7dacb",
          200: "#cbb9a6",
          300: "#a9917c",
          400: "#7e6a58",
          500: "#5c4c3f",
          600: "#443830",
          700: "#302720",
        },
        peach: {
          100: "#faf3ec",
          200: "#f4e8dc",
          300: "#ecdccf",
          400: "#dbc4b2",
        },
        sage: {
          300: "#a8b8a9",
          400: "#879b8b",
          500: "#6b7f70",
        },
      },
      boxShadow: {
        card: "inset 0 1px 0 rgba(255, 244, 231, 0.045), 0 16px 38px rgba(8, 6, 5, 0.28)",
        canvas: "inset 0 1px 0 rgba(255, 250, 244, 0.5), 0 18px 40px rgba(8, 6, 5, 0.26)",
      },
      fontFamily: {
        sans: [
          '"Segoe UI Variable"',
          '"Segoe UI"',
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
