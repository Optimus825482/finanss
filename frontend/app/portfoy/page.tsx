"use client";

import { useEffect, useState, useCallback, FormEvent } from "react";
import { api, AgentPortfolio, AgentDecision } from "../lib/api";

type PortfolioSlug = "bist" | "us";

const PORTFOLIO_LABELS: Record<PortfolioSlug, string> = {
  bist: "BIST 100+",
  us: "US (NASDAQ+DJIA)",
};

export default function PortfoyPage() {
  const [activeTab, setActiveTab] = useState<PortfolioSlug>("bist");
  const [bistPortfolio, setBistPortfolio] = useState<AgentPortfolio | null>(null);
  const [usPortfolio, setUsPortfolio] = useState<AgentPortfolio | null>(null);
  const [portfolio, setPortfolio] = useState<AgentPortfolio | null>(null);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try { setBistPortfolio(await api.getAgentPortfolio("bist")); } catch { /* */ }
    try { setUsPortfolio(await api.getAgentPortfolio("us")); } catch { /* */ }
    try { setPortfolio(await api.getAgentPortfolio(activeTab)); } catch { /* */ }
    try { setDecisions(await api.getAgentDecisions(activeTab, 10)); } catch { /* */ }
  }, [activeTab]);

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { const i = setInterval(loadAll, 60_000); return () => clearInterval(i); }, [loadAll]);

  const handleRun = async (slug: PortfolioSlug) => {
    setRunning(true); setError(null);
    try {
      await api.runAgent(slug);
      let attempts = 0;
      const rapidPoll = setInterval(() => {
        loadAll();
        if (++attempts >= 10) clearInterval(rapidPoll);
      }, 3000);
    }
    catch { setError(`${PORTFOLIO_LABELS[slug]} ajan çalıştırılamadı`); }
    finally { setRunning(false); }
  };

  const borderColor = "var(--term-border)";
  const detSym = activeTab === "bist" ? "₺" : "$";

  const renderSummaryCard = (data: AgentPortfolio | null, slug: PortfolioSlug) => {
    const p = data;
    const sym = slug === "bist" ? "₺" : "$";
    const bgColor = slug === "bist" ? "rgba(245,158,11,0.06)" : "rgba(59,130,246,0.06)";
    const accent = slug === "bist" ? "var(--term-amber)" : "var(--term-blue)";

    return (
      <div className="rounded-sm px-4 py-3 flex-1" style={{ backgroundColor: bgColor, border: `1px solid ${borderColor}` }}>
        <div className="flex items-center justify-between mb-2">
          <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>
            {slug === "bist" ? "🇹🇷 BIST" : "🇺🇸 US"}
            <span className="text-xs ml-1" style={{ color: "var(--term-muted)" }}>{PORTFOLIO_LABELS[slug]}</span>
          </div>
          <button onClick={() => handleRun(slug)} disabled={running}
            className="font-mono text-[10px] px-2 py-1 rounded-sm transition-none disabled:opacity-40"
            style={{ border: `1px solid ${accent}`, color: accent }}>
            {running ? "…" : "▶ ÇALIŞTIR"}
          </button>
        </div>
        {!p ? (
          <div className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>Yükleniyor…</div>
        ) : (
          <div className="grid grid-cols-4 gap-2 text-center">
            <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>NAKİT</div>
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{sym}{(p.cash ?? 0).toFixed(0)}</div></div>
            <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>POZİSYON</div>
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{p.position_count ?? 0}</div></div>
            <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>PİYASA</div>
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{sym}{(p.total_market_value ?? 0).toFixed(0)}</div></div>
            <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>P/L</div>
              <div className="font-mono text-sm font-semibold" style={{ color: (p.total_pl ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                {(p.total_pl ?? 0) >= 0 ? "+" : ""}{sym}{(p.total_pl ?? 0).toFixed(0)}</div></div>
          </div>
        )}
      </div>
    );
  };

  return (
    <main className="min-h-screen px-6 py-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="font-mono text-xl font-semibold mb-1" style={{ color: "var(--term-text)" }}>OTONOM PORTFÖY</h1>
        <p className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>
          İki ayrı otonom ajan: BIST (Türkiye) & US (NASDAQ+DowJones). Her biri 30dk'da bir tarama.
        </p>
      </div>

      <div className="flex gap-4 mb-6">
        {renderSummaryCard(bistPortfolio, "bist")}
        {renderSummaryCard(usPortfolio, "us")}
      </div>

      {error && (
        <div className="rounded-sm px-4 py-2 font-mono text-xs mb-4" style={{ color: "var(--term-red)" }}>{error}</div>
      )}

      {/* Tab selector */}
      <div className="flex gap-1 mb-4">
        {(["bist", "us"] as PortfolioSlug[]).map((slug) => (
          <button key={slug} onClick={() => setActiveTab(slug)}
            className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none"
            style={{ border: "1px solid var(--term-border)", backgroundColor: activeTab === slug ? "var(--term-border)" : "var(--term-bg)",
              color: activeTab === slug ? "var(--term-amber)" : "var(--term-muted)" }}>
            {slug === "bist" ? "🇹🇷 BIST DETAY" : "🇺🇸 US DETAY"}
          </button>
        ))}
      </div>

      {!portfolio ? (
        <div className="rounded-sm p-8 text-center font-mono text-xs" style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)", color: "var(--term-muted)" }}>
          Yükleniyor…
        </div>
      ) : (
        <>
          <div className="rounded-sm px-4 py-3" style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}>
            <div className="grid grid-cols-5 gap-3 text-center">
              <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>NAKİT</div>
                <div className="font-mono text-lg font-semibold" style={{ color: "var(--term-text)" }}>{detSym}{(portfolio.cash ?? 0).toFixed(2)}</div></div>
              <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>MALİYET</div>
                <div className="font-mono text-lg font-semibold" style={{ color: "var(--term-text)" }}>{detSym}{(portfolio.total_cost ?? 0).toFixed(2)}</div></div>
              <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>PİYASA DEĞERİ</div>
                <div className="font-mono text-lg font-semibold" style={{ color: "var(--term-text)" }}>{detSym}{(portfolio.total_market_value ?? 0).toFixed(2)}</div></div>
              <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>P/L</div>
                <div className="font-mono text-lg font-semibold" style={{ color: (portfolio.total_pl ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                  {(portfolio.total_pl ?? 0) >= 0 ? "+" : ""}{detSym}{(portfolio.total_pl ?? 0).toFixed(2)}</div></div>
              <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>P/L %</div>
                <div className="font-mono text-lg font-semibold" style={{ color: (portfolio.total_pl_pct ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                  {(portfolio.total_pl_pct ?? 0).toFixed(1)}%</div></div>
            </div>
          </div>

          {portfolio.positions.length > 0 && (
            <div className="rounded-sm mt-4" style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}>
              <div className="px-4 py-3 text-xs font-mono tracking-wider" style={{ color: "var(--term-muted)", borderBottom: `1px solid ${borderColor}` }}>
                AÇIK POZİSYONLAR ({portfolio.positions.length})
              </div>
              {portfolio.positions.map((pos) => (
                <div key={pos.id} className="flex items-center justify-between px-4 py-3 font-mono text-xs" style={{ borderTop: `1px solid ${borderColor}` }}>
                  <div><span className="font-semibold" style={{ color: "var(--term-text)" }}>{pos.ticker}</span>
                    <span style={{ color: "var(--term-muted)" }}> x{pos.quantity} @ {detSym}{pos.entry_price.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    {pos.current_price && <span style={{ color: "var(--term-muted)" }}>{detSym}{pos.current_price.toFixed(2)}</span>}
                    <span style={{ color: pos.unrealized_pl >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                      {pos.unrealized_pl >= 0 ? "+" : ""}{detSym}{pos.unrealized_pl.toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {decisions.length > 0 && (
            <div className="rounded-sm mt-4" style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}>
              <div className="px-4 py-3 text-xs font-mono tracking-wider" style={{ color: "var(--term-muted)", borderBottom: `1px solid ${borderColor}` }}>
                SON KARARLAR
              </div>
              {decisions.slice(0, 6).map((d) => (
                <div key={d.id} className="flex items-center justify-between px-4 py-2 font-mono text-[11px]" style={{ borderTop: `1px solid ${borderColor}` }}>
                  <div><span className="font-semibold" style={{ color: d.action === "buy" ? "var(--term-green)" : "var(--term-red)" }}>
                    {d.action === "buy" ? "AL" : "SAT"} {d.ticker}</span>
                    <span style={{ color: "var(--term-muted)" }}> x{d.quantity} @ {detSym}{d.price.toFixed(2)}</span>
                  </div>
                  <div className="text-right max-w-[220px] truncate" style={{ color: "var(--term-muted)" }}>{d.reasoning.slice(0, 40)}…</div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <div className="flex gap-3 mt-6">
        <button onClick={() => handleRun("bist")} disabled={running}
          className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none disabled:opacity-40"
          style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>
          ▶ BIST AJANI ÇALIŞTIR
        </button>
        <button onClick={() => handleRun("us")} disabled={running}
          className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none disabled:opacity-40"
          style={{ border: "1px solid var(--term-blue)", color: "var(--term-blue)" }}>
          ▶ US AJANI ÇALIŞTIR
        </button>
      </div>
    </main>
  );
}
