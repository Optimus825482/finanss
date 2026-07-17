"use client";

import { useEffect, useState, useCallback } from "react";
import { api, AgentPortfolio, AgentDecision } from "../lib/api";

export default function AgentPortfolioCard() {
  const [selectedPortfolio, setSelectedPortfolio] = useState<"bist" | "us">("bist");
  const [portfolio, setPortfolio] = useState<AgentPortfolio | null>(null);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPortfolio(await api.getAgentPortfolio(selectedPortfolio));
    } catch { /* agent not configured yet */ }
    try {
      setDecisions(await api.getAgentDecisions(selectedPortfolio, 10));
    } catch { /* no decisions yet */ }
  }, [selectedPortfolio]);

  // Initial load + auto-refresh every 60s + portföy değişince reload
  useEffect(() => {
    load();
    const i = setInterval(load, 60_000);
    return () => clearInterval(i);
  }, [load]);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      await api.runAgent(selectedPortfolio);
      // Wait a moment then refresh
      setTimeout(load, 3000);
    } catch {
      setError("Ajan çalıştırılamadı");
    } finally {
      setRunning(false);
    }
  };

  const borderColor = "var(--term-border)";
  const sym = selectedPortfolio === "bist" ? "₺" : "$";
  const p = portfolio;

  return (
    <div
      className="rounded-sm mt-8"
      style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: `1px solid ${borderColor}` }}>
        <div>
          <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-amber)" }}>
            🤖 OTONOM AJAN
          </div>
          <div className="text-[10px] font-mono mt-0.5" style={{ color: "var(--term-muted)" }}>
            Her 30 dk'da piyasa tarar, otomatik al/sat yapar
          </div>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="px-3 py-1.5 font-mono text-[11px] rounded-sm transition-none disabled:opacity-40 whitespace-nowrap"
          style={{ border: "1px solid var(--term-green)", color: "var(--term-green)" }}
        >
          {running ? "ÇALIŞIYOR…" : "▶ ÇALIŞTIR"}
        </button>
      </div>

      {/* Portföy selector — BIST | US */}
      <div className="flex gap-1 px-4 py-2" style={{ borderBottom: `1px solid ${borderColor}` }}>
        {(["bist", "us"] as const).map((slug) => (
          <button
            key={slug}
            onClick={() => setSelectedPortfolio(slug)}
            className="font-mono text-[11px] tracking-wider px-3 py-1 rounded-sm transition-none"
            style={{
              border: "1px solid var(--term-border)",
              backgroundColor: selectedPortfolio === slug ? "var(--term-border)" : "var(--term-bg)",
              color: selectedPortfolio === slug ? "var(--term-amber)" : "var(--term-muted)",
            }}
          >
            {slug === "bist" ? "BIST" : "US (NASDAQ+DJIA)"}
          </button>
        ))}
      </div>

      {error && (
        <div className="px-4 py-2 font-mono text-[11px]" style={{ color: "var(--term-red)" }}>
          {error}
        </div>
      )}

      {!p ? (
        <div className="px-4 py-6 text-center font-mono text-xs" style={{ color: "var(--term-muted)" }}>
          Ajan başlatılıyor… İlk çalıştırmada portföy oluşur.
        </div>
      ) : (
        <>
          {/* Özet */}
          <div className="grid grid-cols-4 gap-3 px-4 py-3">
            <div className="text-center">
              <div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>NAKİT</div>
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{sym}{p.cash.toFixed(2)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>POZİSYON</div>
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{p.position_count}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>PİYASA D.</div>
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{sym}{p.total_market_value.toFixed(2)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>P/L</div>
              <div className="font-mono text-sm font-semibold" style={{ color: p.total_pl >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                {p.total_pl >= 0 ? "+" : ""}{sym}{p.total_pl.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Ajan pozisyonları */}
          {p.positions.length > 0 && (
            <div style={{ borderTop: `1px solid ${borderColor}` }}>
              <div className="px-4 py-2 text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>
                AJAN POZİSYONLARI
              </div>
              {p.positions.map((pos) => (
                <div
                  key={pos.id}
                  className="flex items-center justify-between px-4 py-2 font-mono text-xs"
                  style={{ borderTop: `1px solid ${borderColor}` }}
                >
                  <div>
                    <span className="font-semibold" style={{ color: "var(--term-text)" }}>{pos.ticker}</span>
                    <span style={{ color: "var(--term-muted)" }}> x{pos.quantity} @ {sym}{pos.entry_price.toFixed(2)}</span>
                  </div>
                  <div style={{ color: pos.unrealized_pl >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                    {pos.unrealized_pl >= 0 ? "+" : ""}{sym}{pos.unrealized_pl.toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Son kararlar */}
      {decisions.length > 0 && (
        <div style={{ borderTop: `1px solid ${borderColor}` }}>
          <div className="px-4 py-2 text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>
            SON KARARLAR
          </div>
          {decisions.slice(0, 6).map((d) => (
            <div
              key={d.id}
              className="flex items-center justify-between px-4 py-1.5 font-mono text-[11px]"
              style={{ borderTop: `1px solid ${borderColor}` }}
            >
              <div>
                <span
                  className="font-semibold"
                  style={{ color: d.action === "buy" ? "var(--term-green)" : "var(--term-red)" }}
                >
                  {d.action === "buy" ? "AL" : "SAT"} {d.ticker}
                </span>
                <span style={{ color: "var(--term-muted)" }}>
                  {" "}x{d.quantity} @ {sym}{d.price.toFixed(2)}
                </span>
              </div>
              <div className="text-right max-w-[200px] truncate" style={{ color: "var(--term-muted)" }}>
                {d.reasoning.slice(0, 40)}…
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
