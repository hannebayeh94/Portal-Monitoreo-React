const { fontFamily } = require("tailwindcss/defaultTheme");

/** @type {import("tailwindcss").Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    container: { center: true, padding: "2rem", screens: { "2xl": "1400px" } },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "#d51b5d",
          foreground: "#ffffff",
          hover: "#b8164e",
          light: "rgba(213, 27, 93, 0.1)"
        },
        secondary: {
          DEFAULT: "#2bbcee",
          foreground: "#ffffff",
          hover: "#24a5d1"
        },
        accent: {
          DEFAULT: "#10004F",
          foreground: "#ffffff",
          light: "rgba(16, 0, 79, 0.08)"
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))"
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))"
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))"
        },
        success: { DEFAULT: "#4caf50", foreground: "#ffffff" },
        warning: { DEFAULT: "#ffb74d", foreground: "#10004F" },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)"
      },
      fontFamily: {
        sans: ["Inter", ...fontFamily.sans],
        mono: ["JetBrains Mono", ...fontFamily.mono]
      },
      keyframes: {
        "fade-in": { from: { opacity: 0 }, to: { opacity: 1 } },
        "slide-in": { from: { transform: "translateX(-10px)", opacity: 0 }, to: { transform: "translateX(0)", opacity: 1 } },
        "scale-in": { from: { transform: "scale(0.95)", opacity: 0 }, to: { transform: "scale(1)", opacity: 1 } }
      },
      animation: {
        "fade-in": "fade-in 0.3s ease-out",
        "slide-in": "slide-in 0.3s ease-out",
        "scale-in": "scale-in 0.2s ease-out"
      }
    }
  },
  plugins: [require("tailwindcss-animate")]
};
