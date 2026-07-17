"use client";

import type { LivePortfolio } from "../lib/api";

interface PortfolioStatusBarProps {
  portfolio: LivePortfolio | null;
  slug: "bist" | "us";
  onToggle: (slug: "bist" | "us") => void;
}

const sym = "₺";

export default function PortfolioStatusBar({
  portfolio,
  slug,
  onToggle,
}: PortfolioStatusBarProps) {
  const borderColor = "var(--term-border)";

  return (
    <div
      className="rounded-sm mb-4"
      style={{
        backgroundColor: "var(--term-panel)",
        border: `1px solid ${borderColor}`,
      }}
    >
      {/* Header row — toggle + label */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ borderBottom: `1px solid ${borderColor}` }}
      >
        <div className="flex items-center gap-3">
          <div
            className="text-[11px] tracking-[0.2em] font-mono"
            style={{ color: "var(--term-muted)" }}
          >
            PORTFÖY DURUMU
          </div>
          <div className="flex gap-1">
            {(["bist", "us"] as const).map((s) => (
              <button
                key={s}
                onClick={() => onToggle(s)}
                className="font-mono text-[10px] tracking-wider px-2 py-0.5 rounded-sm transition-none"
                style={{
                  border: "1px solid var(--term-border)",
                  backgroundColor:
                    slug === s ? "var(--term-border)" : "var(--term-bg)",
                  color:
                    slug === s ? "var(--term-amber)" : "var(--term-muted)",
                }}
              >
                {s === "bist" ? "BIST" : "US"}
              </button>
            ))}
          </div>
        </div>
        <div
          className="text-[10px] font-mono"
          style={{ color: "var(--term-muted)" }}
        >
          CANLI · 3sn
        </div>
      </div>

      {!portfolio ? (
        <div
          className="px-4 py-3 text-center font-mono text-xs"
          style={{ color: "var(--term-muted)" }}
        >
          Ajan başlatılıyor… İlk çalıştırmada portföy oluşur.
        </div>
      ) : (
        <>
          {/* Özet grid */}
          <div className="grid grid-cols-4 gap-2 px-4 py-3">
            <div className="text-center">
              <div
                className="text-[9px] font-mono tracking-wider"
                style={{ color: "var(--term-muted)" }}
              >
                NAKİT
              </div>
              <div
                className="font-mono text-sm font-semibold"
                style={{ color: "var(--term-text)" }}
              >
                {sym}
                {portfolio.cash.toLocaleString("tr-TR", {
                  minimumFractionDigits: 2,
                })}
              </div>
            </div>
            <div className="text-center">
              <div
                className="text-[9px] font-mono tracking-wider"
                style={{ color: "var(--term-muted)" }}
              >
                POZİSYON
              </div>
              <div
                className="font-mono text-sm font-semibold"
                style={{ color: "var(--term-text)" }}
              >
                {portfolio.position_count}
              </div>
            </div>
            <div className="text-center">
              <div
                className="text-[9px] font-mono tracking-wider"
                style={{ color: "var(--term-muted)" }}
              >
                PİYASA D.
              </div>
              <div
                className="font-mono text-sm font-semibold"
                style={{ color: "var(--term-text)" }}
              >
                {sym}
                {portfolio.total_market_value.toLocaleString("tr-TR", {
                  minimumFractionDigits: 2,
                })}
              </div>
            </div>
            <div className="text-center">
              <div
                className="text-[9px] font-mono tracking-wider"
                style={{ color: "var(--term-muted)" }}
              >
                P/L
              </div>
              <div
                className="font-mono text-sm font-semibold"
                style={{
                  color:
                    portfolio.total_pl >= 0
                      ? "var(--term-green)"
                      : "var(--term-red)",
                }}
              >
                {portfolio.total_pl >= 0 ? "+" : ""}
                {sym}
                {portfolio.total_pl.toLocaleString("tr-TR", {
                  minimumFractionDigits: 2,
                })}{" "}
                <span className="text-[10px]">
                  (%{portfolio.total_pl_pct.toFixed(1)})
                </span>
              </div>
            </div>
          </div>

          {/* Mini pozisyon listesi (ilk 3) */}
          {portfolio.positions.length > 0 && (
            <div style={{ borderTop: `1px solid ${borderColor}` }}>
              <div className="flex gap-3 px-4 py-2 overflow-x-auto">
                {portfolio.positions.slice(0, 3).map((pos) => (
                  <div
                    key={pos.id}
                    className="font-mono text-[11px] shrink-0"
                    style={{ color: "var(--term-text)" }}
                  >
                    <span className="font-semibold">
                      {pos.ticker.replace(".IS", "")}
                    </span>{" "}
                    <span style={{ color: "var(--term-muted)" }}>
                      x{pos.quantity}
                    </span>{" "}
                    <span
                      style={{
                        color:
                          pos.unrealized_pl >= 0
                            ? "var(--term-green)"
                            : "var(--term-red)",
                      }}
                    >
                      {pos.unrealized_pl >= 0 ? "+" : ""}
                      {sym}
                      {pos.unrealized_pl.toFixed(0)}
                    </span>
                  </div>
                ))}
                {portfolio.positions.length > 3 && (
                  <span
                    className="font-mono text-[11px] shrink-0"
                    style={{ color: "var(--term-muted)" }}
                  >
                    +{portfolio.positions.length - 3} daha
                  </span>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
