import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f6f7f8",
          100: "#ebedf0",
          200: "#d6dbe1",
          300: "#b4bdc9",
          400: "#7e8b9f",
          500: "#5b6779",
          600: "#404b5d",
          700: "#2b3442",
          800: "#1c232d",
          900: "#12171f"
        },
        signal: {
          50: "#ecfeff",
          100: "#cffafe",
          200: "#a5f3fc",
          300: "#67e8f9",
          400: "#22d3ee",
          500: "#06b6d4",
          600: "#0891b2",
          700: "#0e7490",
          800: "#155e75",
          900: "#164e63"
        }
      },
      boxShadow: {
        panel: "0 18px 40px rgba(17, 24, 39, 0.08)"
      },
      fontFamily: {
        sans: ["Segoe UI Variable", "Aptos", "Trebuchet MS", "Segoe UI", "sans-serif"]
      },
      backgroundImage: {
        "surface-gradient":
          "radial-gradient(circle at top left, rgba(6, 182, 212, 0.12), transparent 35%), radial-gradient(circle at bottom right, rgba(20, 184, 166, 0.08), transparent 30%)"
      }
    }
  },
  plugins: []
} satisfies Config;
