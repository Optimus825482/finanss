"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

const NAV_ITEMS = [
  { label: "ANA SAYFA", href: "/" },
  { label: "PORTFÖY", href: "/portfoy" },
  { label: "SEMBOL ANALİZ", href: "/skill" },
  { label: "TAKİP", href: "/takip" },
  { label: "RAPORLAR", href: "/raporlar" },
  { label: "AYARLAR", href: "/ayarlar" },
];

/** BIST açılış/kapanış saatleri (UTC+3) */
function bistMarketStatus(now: Date): { open: boolean; label: string } {
  const day = now.getDay(); // 0=Pazar, 6=Cumartesi
  const hour = now.getHours();
  const minute = now.getMinutes();
  const t = hour * 60 + minute;

  if (day === 0 || day === 6) return { open: false, label: "BIST KAPALI" };
  // BIST: 10:00-18:00, öğle arası 12:55-14:00 (opsiyonel)
  if (t < 600 || t >= 1080) return { open: false, label: "BIST KAPALI" };
  return { open: true, label: "BIST AÇIK" };
}

/** ABD borsaları (NASDAQ/NYSE) açılış/kapanış — UTC+3 (EDT=UTC-4 → yaz saati UTC+3'te 16:30-23:00) */
function usMarketStatus(now: Date): { open: boolean; label: string } {
  const day = now.getDay();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const t = hour * 60 + minute;

  if (day === 0 || day === 6) return { open: false, label: "US KAPALI" };
  // US: 16:30-23:00 Istanbul time (EDT yaz saati)
  if (t >= 990 && t < 1380) return { open: true, label: "US AÇIK" };
  return { open: false, label: "US KAPALI" };
}

function formatTime(now: Date): string {
  const h = String(now.getHours()).padStart(2, "0");
  const m = String(now.getMinutes()).padStart(2, "0");
  const s = String(now.getSeconds()).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

export default function Navbar() {
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [timeStr, setTimeStr] = useState("");
  const [bist, setBist] = useState({ open: false, label: "" });
  const [us, setUs] = useState({ open: false, label: "" });

  const loadUnread = async () => {
    try {
      const r = await api.getUnreadCount();
      setUnread(r.count ?? 0);
    } catch (e) { console.warn("Failed to load unread count", e); }
  };

  // Clock tick
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTimeStr(formatTime(now));
      setBist(bistMarketStatus(now));
      setUs(usMarketStatus(now));
    };
    tick();
    const i = setInterval(tick, 1000);
    return () => clearInterval(i);
  }, []);

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

  const dotColor = (open: boolean) => ({
    width: 6, height: 6, borderRadius: "50%", display: "inline-block",
    backgroundColor: open ? "#22c55e" : "#ef4444",
    boxShadow: open ? "0 0 6px #22c55e" : "none",
  });

  return (
    <nav className="sticky top-0 z-50 border-b backdrop-blur-sm" style={{ backgroundColor: "var(--term-panel)", borderColor: "var(--term-border)" }}>
      <div className="max-w-6xl mx-auto flex items-center justify-between px-3 sm:px-6 py-0">
        {/* Desktop nav */}
        <div className="hidden sm:flex items-center gap-1">
          {NAV_ITEMS.map(item => navLink(item.href, item.label))}
        </div>

        {/* Mobile hamburger */}
        <button onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen}
          className="sm:hidden font-mono text-lg px-2 py-3 transition-none"
          style={{ color: "var(--term-amber)" }}>
          {menuOpen ? "✕" : "☰"}
        </button>

        {/* Right side: Market status + Clock + Theme */}
        <div className="flex items-center gap-3 sm:gap-4">
          {/* BIST indicator */}
          <div className="hidden sm:flex items-center gap-1.5">
            <span style={dotColor(bist.open)} />
            <span className="font-mono text-[9px] sm:text-[10px] tracking-wider"
              style={{ color: bist.open ? "var(--term-green)" : "var(--term-muted)" }}>
              {bist.label}
            </span>
          </div>

          {/* US indicator */}
          <div className="hidden sm:flex items-center gap-1.5">
            <span style={dotColor(us.open)} />
            <span className="font-mono text-[9px] sm:text-[10px] tracking-wider"
              style={{ color: us.open ? "var(--term-green)" : "var(--term-muted)" }}>
              {us.label}
            </span>
          </div>

          {/* Digital clock */}
          <div className="font-mono text-[11px] sm:text-xs font-bold tracking-wider tabular-nums select-none"
            style={{ color: "var(--term-amber)" }}>
            {timeStr}
          </div>

          <ThemeToggle />
        </div>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="sm:hidden flex flex-col border-t" style={{ borderColor: "var(--term-border)" }}>
          {NAV_ITEMS.map(item => navLink(item.href, item.label))}
          {/* Mobile market indicators */}
          <div className="flex items-center gap-3 px-3 py-2 border-t" style={{ borderColor: "var(--term-border)" }}>
            <span style={dotColor(bist.open)} />
            <span className="font-mono text-[10px]" style={{ color: bist.open ? "var(--term-green)" : "var(--term-muted)" }}>{bist.label}</span>
            <span style={dotColor(us.open)} />
            <span className="font-mono text-[10px]" style={{ color: us.open ? "var(--term-green)" : "var(--term-muted)" }}>{us.label}</span>
          </div>
        </div>
      )}
    </nav>
  );
}
