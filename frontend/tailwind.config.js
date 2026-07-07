/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        term: {
          bg: "var(--term-bg)",
          panel: "var(--term-panel)",
          border: "var(--term-border)",
          amber: "var(--term-amber)",
          amberDim: "var(--term-amber-dim)",
          green: "var(--term-green)",
          red: "var(--term-red)",
          text: "var(--term-text)",
          muted: "var(--term-muted)",
        },
      },
      fontFamily: {
        mono: ["IBM Plex Mono", "JetBrains Mono", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 12px var(--term-glow)",
      },
    },
  },
  plugins: [],
};
