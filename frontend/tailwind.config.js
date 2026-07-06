/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        term: {
          bg: "#0B0E11",
          panel: "#12161B",
          border: "#23292F",
          amber: "#FFB000",
          amberDim: "#8A6100",
          green: "#4ADE80",
          red: "#F87171",
          text: "#D9D9D0",
          muted: "#6B7280",
        },
      },
      fontFamily: {
        mono: ["IBM Plex Mono", "JetBrains Mono", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 12px rgba(255, 176, 0, 0.35)",
      },
    },
  },
  plugins: [],
};
