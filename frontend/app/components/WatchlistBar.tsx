"use client";

import Link from "next/link";
import type { LiveWatchlistItem } from "../lib/api";

interface WatchlistBarProps {
  items: LiveWatchlistItem[];
}

/** BIST hisseleri .IS ile biter — ₺, diğerleri $ */
function currencySymbol(ticker: string): string {
  return ticker.endsWith(".IS") ? "₺" : "$";
}

export default function WatchlistBar({ items }: WatchlistBarProps) {
  if (items.length === 0) {
    return (
      <div
        className="rounded-sm px-4 py-3 mb-4 text-center font-mono text-xs"
        style={{
          backgroundColor: "var(--term-panel)",
          border: "1px solid var(--term-border)",
          color: "var(--term-muted)",
        }}
      >
        Takip listeniz boş.{" "}
        <Link href="/takip" style={{ color: "var(--term-amber)" }}>
          /takip sayfasından hisse ekleyin →
        </Link>
      </div>
    );
  }

  return (
    <div
      className="rounded-sm mb-4"
      style={{
        backgroundColor: "var(--term-panel)",
        border: "1px solid var(--term-border)",
      }}
    >
      <div className="flex items-center justify-between px-4 py-2">
        <div
          className="text-[11px] tracking-[0.2em] font-mono"
          style={{ color: "var(--term-muted)" }}
        >
          TAKİP LİSTESİ
        </div>
        <Link
          href="/takip"
          className="text-xs font-mono transition-none"
          style={{ color: "var(--term-amber)" }}
        >
          TÜMÜNÜ GÖR →
        </Link>
      </div>
      <div className="flex gap-2 px-4 pb-3 overflow-x-auto">
        {items.map((it) => {
          const sym = currencySymbol(it.ticker);
          const change = it.change_pct ?? 0;
          const isUp = change >= 0;
          return (
            <Link
              key={it.id}
              href="/takip"
              className="rounded-sm px-3 py-2 text-center transition-none shrink-0 min-w-[90px] block"
              style={{
                backgroundColor: "var(--term-bg)",
                border: "1px solid var(--term-border)",
              }}
            >
              <div
                className="font-mono text-sm font-semibold"
                style={{ color: "var(--term-text)" }}
              >
                {it.ticker.replace(".IS", "")}
              </div>
              {it.price !== null ? (
                <div
                  className="font-mono text-xs mt-0.5"
                  style={{ color: "var(--term-text)" }}
                >
                  {sym}
                  {it.price.toFixed(2)}
                  <span
                    className="ml-1"
                    style={{
                      color: isUp ? "var(--term-green)" : "var(--term-red)",
                    }}
                  >
                    {isUp ? "▲" : "▼"}
                    {Math.abs(change).toFixed(1)}%
                  </span>
                </div>
              ) : (
                <div
                  className="text-xs font-mono mt-0.5"
                  style={{ color: "var(--term-muted)" }}
                >
                  —
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
