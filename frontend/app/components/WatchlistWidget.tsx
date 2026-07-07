"use client";

import Link from "next/link";
import type { WatchlistItem } from "../lib/api";

interface WatchlistWidgetProps {
  watchlist: WatchlistItem[];
}

export default function WatchlistWidget({ watchlist }: WatchlistWidgetProps) {
  if (watchlist.length === 0) return null;

  return (
    <div className="mt-6">
      <div className="rounded-sm p-4" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
        <div className="flex items-center justify-between mb-3">
          <div className="text-[11px] tracking-[0.2em] font-mono" style={{ color: "var(--term-muted)" }}>
            TAKİP LİSTESİ
          </div>
          <Link href="/takip" className="text-xs font-mono transition-none" style={{ color: "var(--term-amber)" }}>
            TÜMÜNÜ GÖR →
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
          {watchlist.slice(0, 5).map((it) => (
            <Link key={it.id} href="/takip"
              className="rounded-sm px-3 py-2.5 text-center transition-none block"
              style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)" }}>
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{it.ticker}</div>
              {it.price !== null ? (
                <div className="font-mono text-xs mt-0.5" style={{ color: "var(--term-text)" }}>
                  ${it.price.toFixed(2)}
                  <span className="ml-1" style={{ color: (it.change_pct ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                    {it.change_pct !== null ? `${it.change_pct >= 0 ? "▲" : "▼"}${Math.abs(it.change_pct)}%` : "—"}
                  </span>
                </div>
              ) : (
                <div className="text-xs font-mono mt-0.5" style={{ color: "var(--term-muted)" }}>—</div>
              )}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
