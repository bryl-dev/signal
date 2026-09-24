import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0b0c0e",
          900: "#121418",
          800: "#1a1d23",
          700: "#262a31",
        },
        paper: {
          50: "#f6f1e6",
          100: "#ece7db",
          400: "#9a9386",
        },
        signal: {
          400: "#e4b44c",
          500: "#d4a017",
        },
      },
      fontFamily: {
        display: ["Georgia", "Times New Roman", "serif"],
        sans: ["Segoe UI", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
