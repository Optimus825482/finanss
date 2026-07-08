"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";
import { useEffect, useState } from "react";

const NAV_ITEMS = [
  { label: "ANA SAYFA", href: "/" },
  { label: "İZLEME", href: "/izleme" },
  { label: "PORTFÖY", href: "/portfoy" },
  { label: "TAKİP", href: "/takip" },
  { label: "RAPORLAR", href: "/raporlar" },
  { label: "AYARLAR", href: "/ayarlar" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);

	const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8012";

	const loadUnread = async () => {
	    try {
	      const r = await fetch(`${apiBase}/api/notifications/unread-count`);
	      if (r.ok) setUnread((await r.json()).count ?? 0);
	    } catch (e) { console.warn("Failed to load unread count", e); }
	  };

  useEffect(() => { loadUnread(); const i = setInterval(loadUnread, 30_000); return () => clearInterval(i); }, []);

		  useEffect(() => { setMenuOpen(false); }, [pathname]);

  const navLink = (href: string, label: string) => {
    const active = pathname === href;
    return (
      <Link key={href} href={href}
        className="font-mono text-[11px] sm:text-xs tracking-wider px-2 sm:px-3 py-3 sm:py-4 border-b-2 transition-none whitespace-nowrap"
        style={{
          color: active ? "var(--term-amber)" : "var(--term-muted)",
          borderBottomColor: active ? "var(--term-amber)" : "transparent",
          fontWeight: active ? 600 : 400,
        }}>
        {label}
        {href === "/raporlar" && unread > 0 && (
          <span className="ml-1.5 px-1.5 py-0.5 rounded-sm text-[9px] font-bold animate-pulse"
            style={{ backgroundColor: "var(--term-red)", color: "#fff" }}>{unread}</span>
        )}
      </Link>
    );
  };

  return (
    <nav className="sticky top-0 z-50 border-b backdrop-blur-sm" style={{ backgroundColor: "var(--term-panel)", borderColor: "var(--term-border)" }}>
      <div className="max-w-6xl mx-auto flex items-center justify-between px-3 sm:px-6 py-0">
        {/* Desktop nav */}
        <div className="hidden sm:flex items-center gap-1">
          {NAV_ITEMS.map(item => navLink(item.href, item.label))}
        </div>

        {/* Mobile hamburger */}
        <button onClick={() => setMenuOpen(!menuOpen)} className="sm:hidden font-mono text-lg px-2 py-3 transition-none"
          style={{ color: "var(--term-amber)" }}>
          {menuOpen ? "✕" : "☰"}
        </button>

        <ThemeToggle />
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="sm:hidden flex flex-col border-t" style={{ borderColor: "var(--term-border)" }}>
          {NAV_ITEMS.map(item => navLink(item.href, item.label))}
        </div>
      )}
    </nav>
  );
}
