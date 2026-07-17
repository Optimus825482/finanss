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

type MarketInfo = { open: boolean; label: string; countdown: string | null };

function fmtCountdown(seconds: number): string {
  if (seconds <= 0) return "00:00:00";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** BIST açılış/kapanış saatleri (UTC+3) — 10:00-18:00 */
const BIST_OPEN = 600;  // 10:00
const BIST_CLOSE = 1080; // 18:00

function bistMarketStatus(now: Date): MarketInfo {
  const day = now.getDay();
  const t = now.getHours() * 60 + now.getMinutes();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  if (day === 0 || day === 6) return { open: false, label: "BIST KAPALI", countdown: null };

  if (t >= BIST_OPEN && t < BIST_CLOSE) {
    // Açık → kapanışa kalan
    const close = new Date(today); close.setHours(18, 0, 0, 0);
    const diff = Math.floor((close.getTime() - now.getTime()) / 1000);
    return { open: true, label: "BIST AÇIK", countdown: fmtCountdown(diff) };
  }

  // Kapalı → açılışa kalan
  let openTarget: Date;
  if (t >= BIST_CLOSE) {
    // Bugün kapandı → yarın 10:00
    openTarget = new Date(today); openTarget.setDate(openTarget.getDate() + 1);
  } else {
    // Henüz açılmadı → bugün 10:00
    openTarget = new Date(today);
  }
  openTarget.setHours(10, 0, 0, 0);
  const diff = Math.floor((openTarget.getTime() - now.getTime()) / 1000);
  return { open: false, label: "BIST KAPALI", countdown: fmtCountdown(diff) };
}

/** ABD borsaları (NASDAQ/NYSE) — UTC+3: 16:30-23:00 (EDT yaz saati) */
const US_OPEN = 990;   // 16:30
const US_CLOSE = 1380; // 23:00

function usMarketStatus(now: Date): MarketInfo {
  const day = now.getDay();
  const t = now.getHours() * 60 + now.getMinutes();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  if (day === 0 || day === 6) return { open: false, label: "US KAPALI", countdown: null };

  if (t >= US_OPEN && t < US_CLOSE) {
    // Açık → kapanışa kalan
    const close = new Date(today); close.setHours(23, 0, 0, 0);
    const diff = Math.floor((close.getTime() - now.getTime()) / 1000);
    return { open: true, label: "US AÇIK", countdown: fmtCountdown(diff) };
  }

  // Kapalı → açılışa kalan
  let openTarget: Date;
  if (t >= US_CLOSE) {
    // Bugün kapandı → yarın 16:30
    openTarget = new Date(today); openTarget.setDate(openTarget.getDate() + 1);
  } else {
    // Henüz açılmadı → bugün 16:30
    openTarget = new Date(today);
  }
  openTarget.setHours(16, 30, 0, 0);
  const diff = Math.floor((openTarget.getTime() - now.getTime()) / 1000);
  return { open: false, label: "US KAPALI", countdown: fmtCountdown(diff) };
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
  const [bist, setBist] = useState<MarketInfo>({ open: false, label: "", countdown: null });
  const [us, setUs] = useState<MarketInfo>({ open: false, label: "", countdown: null });

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

  const marketLabel = (info: MarketInfo) => (
    <span className="flex items-center gap-1">
      <span style={dotColor(info.open)} />
      <span className="font-mono text-[9px] sm:text-[10px] tracking-wider"
        style={{ color: info.open ? "var(--term-green)" : "var(--term-muted)" }}>
        {info.label}
      </span>
      {info.countdown && (
        <span className="font-mono text-[9px] sm:text-[10px] tabular-nums ml-0.5"
          style={{ color: "var(--term-amber-dim)" }}>
          · {info.countdown}
        </span>
      )}
    </span>
  );

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
            {marketLabel(bist)}
          </div>

          {/* US indicator */}
          <div className="hidden sm:flex items-center gap-1.5">
            {marketLabel(us)}
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
            {marketLabel(bist)}
            {marketLabel(us)}
          </div>
        </div>
      )}
    </nav>
  );
}
