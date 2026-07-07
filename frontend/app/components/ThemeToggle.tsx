"use client";

import { useState, useEffect } from "react";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const stored = localStorage.getItem("orbis-theme") as "dark" | "light" | null;
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    setTheme(stored || (prefersDark ? "dark" : "light"));
  }, []);

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("orbis-theme", next);
    document.documentElement.setAttribute(
      "data-theme",
      next === "light" ? "light" : ""
    );
  };

  return (
    <button
      onClick={toggle}
      className="theme-toggle font-mono text-xs tracking-wider px-3 py-1.5 border rounded-sm transition-colors ml-3"
      style={{
        borderColor: "var(--term-border)",
        color: "var(--term-muted)",
        backgroundColor: "var(--term-panel)",
      }}
      aria-label={theme === "dark" ? "Aydınlık tema" : "Karanlık tema"}
    >
      {theme === "dark" ? "☀ LIGHT" : "◉ DARK"}
    </button>
  );
}
