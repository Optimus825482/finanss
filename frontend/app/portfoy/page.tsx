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
  const [runId, setRunId] = useState<string | null>(null);
  const [logs, setLogs] = useState<Array<{step: string; msg: string; ts: number}>>([]);
  const [logStatus, setLogStatus] = useState<string>("");
  const [showHistory, setShowHistory] = useState(false);

  const loadAll = useCallback(async () => {
    try { setBistPortfolio(await api.getAgentPortfolio("bist")); } catch { /* */ }
    try { setUsPortfolio(await api.getAgentPortfolio("us")); } catch { /* */ }
    try { setPortfolio(await api.getAgentPortfolio(activeTab)); } catch { /* */ }
    try { setDecisions(await api.getAgentDecisions(activeTab, 10)); } catch { /* */ }
  }, [activeTab]);

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { const i = setInterval(loadAll, 60_000); return () => clearInterval(i); }, [loadAll]);

  const handleRun = async (slug: PortfolioSlug) => {
    setRunning(true); setError(null); setLogs([]); setLogStatus("running");
    try {
      const res = await api.runAgent(slug);
      const rid = (res as any).run_id;
      if (rid) {
        setRunId(rid);
        // Poll logs every 2s
        const logPoll = setInterval(async () => {
          try {
            const r = await fetch(`/api/autonomous/logs/${rid}`);
            const d = await r.json();
            setLogs(d.steps || []);
            setLogStatus(d.status || "");
            loadAll();
            if (d.status === "done" || d.status === "error") {
              clearInterval(logPoll);
              setRunning(false);
              loadAll();
            }
          } catch { /* */ }
        }, 2000);
      } else {
        // Fallback: no run_id from backend
        let attempts = 0;
        const rapidPoll = setInterval(() => {
          loadAll();
          if (++attempts >= 10) { clearInterval(rapidPoll); setRunning(false); }
        }, 3000);
      }
    }
    catch { setError(`${PORTFOLIO_LABELS[slug]} ajan çalıştırılamadı`); setRunning(false); }
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
              {portfolio.positions.map((pos) => {
                const chg = pos.change_pct ?? 0;
                const chgColor = chg > 0 ? "var(--term-green)" : chg < 0 ? "var(--term-red)" : "var(--term-muted)";
                const chgSign = chg > 0 ? "▲" : chg < 0 ? "▼" : "";
                return (
                <div key={pos.id} className="flex items-center justify-between px-4 py-3 font-mono text-xs" style={{ borderTop: `1px solid ${borderColor}` }}>
                  <div>
                    <span className="font-semibold" style={{ color: chgColor }}>{pos.ticker}</span>
                    <span style={{ color: chgColor, marginLeft: 4, fontSize: "10px" }}>
                      {chgSign}{Math.abs(chg).toFixed(1)}%
                    </span>
                    <span style={{ color: "var(--term-muted)" }}> x{pos.quantity} @ {detSym}{pos.entry_price.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    {pos.current_price && <span style={{ color: "var(--term-muted)" }}>{detSym}{pos.current_price.toFixed(2)}</span>}
                    <span style={{ color: pos.unrealized_pl >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                      {pos.unrealized_pl >= 0 ? "+" : ""}{detSym}{pos.unrealized_pl.toFixed(2)}
                    </span>
                  </div>
                </div>
                );
              })}
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

      {/* Agent execution log */}
      {logs.length > 0 && (
        <div className="rounded-sm mt-4" style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}>
          <div className="px-4 py-2 text-xs font-mono tracking-wider flex items-center justify-between"
            style={{ color: "var(--term-muted)", borderBottom: `1px solid ${borderColor}` }}>
            <span>AJAN ÇALIŞMA LOGU</span>
            <span style={{ color: logStatus === "running" ? "var(--term-green)" : logStatus === "error" ? "var(--term-red)" : "var(--term-amber)" }}>
              {logStatus === "running" ? "● ÇALIŞIYOR" : logStatus === "done" ? "✓ TAMAMLANDI" : logStatus === "error" ? "✕ HATA" : logStatus}
            </span>
          </div>
          <div className="px-4 py-2 max-h-48 overflow-y-auto">
            {logs.map((l, i) => (
              <div key={i} className="font-mono text-[11px] py-0.5" style={{ color: l.step === "error" ? "var(--term-red)" : l.step === "trade" ? "var(--term-green)" : "var(--term-text)" }}>
                <span className="text-[9px] mr-2" style={{ color: "var(--term-muted)" }}>
                  {new Date(l.ts * 1000).toLocaleTimeString("tr-TR")}
                </span>
                {l.msg}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trade History Button + Modal */}
      <div className="mt-6">
        <button onClick={() => setShowHistory(true)}
          className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none"
          style={{ border: "1px solid var(--term-border)", color: "var(--term-muted)" }}>
          📋 TRADE GEÇMİŞİ
        </button>
      </div>

      {showHistory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.7)" }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowHistory(false); }}>
          <div className="rounded-sm w-full max-w-3xl max-h-[80vh] overflow-y-auto mx-4" 
            style={{ backgroundColor: "var(--term-panel)", border: `1px solid ${borderColor}` }}>
            <div className="sticky top-0 flex items-center justify-between px-4 py-3"
              style={{ backgroundColor: "var(--term-panel)", borderBottom: `1px solid ${borderColor}` }}>
              <div className="font-mono text-sm" style={{ color: "var(--term-amber)" }}>📋 TRADE GEÇMİŞİ</div>
              <button onClick={() => setShowHistory(false)}
                className="font-mono text-lg px-2" style={{ color: "var(--term-muted)" }}>✕</button>
            </div>
            <div className="p-2">
              <table className="w-full font-mono text-[11px]">
                <thead>
                  <tr style={{ color: "var(--term-muted)", borderBottom: `1px solid ${borderColor}` }}>
                    <th className="text-left px-2 py-2">Tarih</th>
                    <th className="text-left px-2 py-2">Hisse</th>
                    <th className="text-left px-2 py-2">İşlem</th>
                    <th className="text-right px-2 py-2">Adet</th>
                    <th className="text-right px-2 py-2">Fiyat</th>
                    <th className="text-right px-2 py-2">Tutar</th>
                    <th className="text-right px-2 py-2">K/Z</th>
                  </tr>
                </thead>
                <tbody>
                  {decisions.map((d, i) => {
                    const isBuy = d.action === "buy";
                    // K/Z: sell'lerde total_amount göster (proceeds), buy'larda -
                    const pl = !isBuy ? (d.total_amount || 0) - (d.quantity * d.price) : null;
                    return (
                      <tr key={d.id || i} style={{ color: "var(--term-text)", borderTop: `1px solid ${borderColor}` }}>
                        <td className="px-2 py-1.5" style={{ color: "var(--term-muted)" }}>
                          {new Date(d.created_at).toLocaleDateString("tr-TR")} {new Date(d.created_at).toLocaleTimeString("tr-TR", {hour:"2-digit", minute:"2-digit"})}
                        </td>
                        <td className="px-2 py-1.5 font-semibold">{d.ticker}</td>
                        <td className="px-2 py-1.5" style={{ color: isBuy ? "var(--term-green)" : "var(--term-red)" }}>
                          {isBuy ? "ALIM" : "SATIM"}
                        </td>
                        <td className="px-2 py-1.5 text-right">{d.quantity}</td>
                        <td className="px-2 py-1.5 text-right">{detSym}{d.price.toFixed(2)}</td>
                        <td className="px-2 py-1.5 text-right">{detSym}{d.total_amount.toFixed(2)}</td>
                        <td className="px-2 py-1.5 text-right" style={{ color: pl != null ? (pl >= 0 ? "var(--term-green)" : "var(--term-red)") : "var(--term-muted)" }}>
                          {pl != null ? `${pl >= 0 ? "+" : ""}${detSym}${pl.toFixed(0)}` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
