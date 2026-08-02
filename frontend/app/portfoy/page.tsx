"use client";

import { useEffect, useState, useCallback } from "react";
import { api, AgentPortfolio, AgentDecision, CryptoKline, CryptoAnalysis } from "../lib/api";
import CryptoChart from "../components/CryptoChart";

type PortfolioSlug = "bist" | "us" | "crypto";

const PORTFOLIO_LABELS: Record<PortfolioSlug, string> = {
  bist: "BIST 100+",
  us: "US (NASDAQ+DJIA)",
  crypto: "Kripto (Binance)",
};

const PORTFOLIO_ICONS: Record<PortfolioSlug, string> = {
  bist: "🇹🇷",
  us: "🇺🇸",
  crypto: "₿",
};

const PORTFOLIO_SYMS: Record<PortfolioSlug, string> = {
  bist: "₺",
  us: "$",
  crypto: "$",
};

const PORTFOLIO_ACCENTS: Record<PortfolioSlug, string> = {
  bist: "var(--term-amber)",
  us: "var(--term-blue)",
  crypto: "var(--term-green)",
};

export default function PortfoyPage() {
  const [activeTab, setActiveTab] = useState<PortfolioSlug>("bist");
  const [portfolios, setPortfolios] = useState<Record<PortfolioSlug, AgentPortfolio | null>>({
    bist: null, us: null, crypto: null,
  });
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  // Crypto: M5 grafik + analiz
  const [cryptoKlines, setCryptoKlines] = useState<CryptoKline[]>([]);
  const [cryptoAnalysis, setCryptoAnalysis] = useState<CryptoAnalysis | null>(null);
  const [cryptoChartSymbol, setCryptoChartSymbol] = useState("BTCUSDT");
  const [cryptoUniverse, setCryptoUniverse] = useState<string[]>([]);
  const [cryptoLoading, setCryptoLoading] = useState(false);

  const loadAll = useCallback(async () => {
    for (const slug of ["bist", "us", "crypto"] as PortfolioSlug[]) {
      try {
        const p = await api.getAgentPortfolio(slug);
        setPortfolios(prev => ({ ...prev, [slug]: p }));
      } catch { /* */ }
    }
    try { setDecisions(await api.getAgentDecisions(activeTab, 15)); } catch { /* */ }
  }, [activeTab]);

  const loadCrypto = useCallback(async () => {
    try {
      const u = await api.cryptoUniverse();
      setCryptoUniverse(u.symbols);
    } catch { /* */ }
  }, []);

  const loadCryptoChart = useCallback(async (symbol: string) => {
    setCryptoLoading(true);
    try {
      const [k, a] = await Promise.all([
        api.cryptoKlines(symbol, "5m", 120),
        api.cryptoAnalyze(symbol, "5m"),
      ]);
      setCryptoKlines(k.klines);
      setCryptoAnalysis(a);
    } catch (e) {
      setError(`Kripto grafik yüklenemedi: ${e instanceof Error ? e.message : "?"}`);
    } finally {
      setCryptoLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { const i = setInterval(loadAll, 60_000); return () => clearInterval(i); }, [loadAll]);
  useEffect(() => { loadCrypto(); }, [loadCrypto]);

  // Crypto sekmesi açılınca BTC grafiğini yükle + 30s canlı güncelle
  useEffect(() => {
    if (activeTab !== "crypto") return;
    loadCryptoChart(cryptoChartSymbol);
    const i = setInterval(() => loadCryptoChart(cryptoChartSymbol), 30_000);
    return () => clearInterval(i);
  }, [activeTab, cryptoChartSymbol, loadCryptoChart]);

  const handleRun = async (slug: PortfolioSlug) => {
    setRunning(true); setError(null);
    try {
      await api.runAgent(slug);
      // Ajan arka planda çalışıyor — 5s sonra durumu tazele
      setTimeout(async () => { await loadAll(); setRunning(false); }, 5000);
    } catch {
      setError(`${PORTFOLIO_LABELS[slug]} ajan çalıştırılamadı`);
      setRunning(false);
    }
  };

  const borderColor = "var(--term-border)";
  const activePortfolio = portfolios[activeTab];
  const detSym = PORTFOLIO_SYMS[activeTab];
  const accent = PORTFOLIO_ACCENTS[activeTab];

  const renderSummaryCard = (data: AgentPortfolio | null, slug: PortfolioSlug) => {
    const sym = PORTFOLIO_SYMS[slug];
    const bgColor = slug === "bist" ? "rgba(245,158,11,0.06)"
      : slug === "us" ? "rgba(59,130,246,0.06)" : "rgba(34,197,94,0.06)";
    const cardAccent = PORTFOLIO_ACCENTS[slug];

    return (
      <div className="rounded-sm px-4 py-3 flex-1" style={{ backgroundColor: bgColor, border: `1px solid ${borderColor}` }}>
        <div className="flex items-center justify-between mb-2">
          <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>
            {PORTFOLIO_ICONS[slug]} {slug === "bist" ? "BIST" : slug === "us" ? "US" : "KRİPTO"}
            <span className="text-xs ml-1" style={{ color: "var(--term-muted)" }}>{PORTFOLIO_LABELS[slug]}</span>
          </div>
          <button onClick={() => handleRun(slug)} disabled={running}
            className="font-mono text-[10px] px-2 py-1 rounded-sm transition-none disabled:opacity-40"
            style={{ border: `1px solid ${cardAccent}`, color: cardAccent }}>
            {running ? "…" : "▶ ÇALIŞTIR"}
          </button>
        </div>
        {!data ? (
          <div className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>Yükleniyor…</div>
        ) : (
          <div className="grid grid-cols-4 gap-2 text-center">
            <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>NAKİT</div>
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{sym}{(data.cash ?? 0).toFixed(0)}</div></div>
            <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>POZİSYON</div>
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{data.position_count ?? 0}</div></div>
            <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>PİYASA</div>
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{sym}{(data.total_market_value ?? 0).toFixed(0)}</div></div>
            <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>P/L</div>
              <div className="font-mono text-sm font-semibold" style={{ color: (data.total_pl ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                {(data.total_pl ?? 0) >= 0 ? "+" : ""}{sym}{(data.total_pl ?? 0).toFixed(0)}</div></div>
          </div>
        )}
      </div>
    );
  };

  return (
    <main className="min-h-screen px-6 py-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="font-mono text-xl font-semibold mb-1" style={{ color: "var(--term-text)" }}>OTONOM PORTFÖY</h1>
        <p className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>
          Üç ayrı otonom ajan: BIST (30dk), US (30dk) & Kripto Binance (15dk, 7/24).
        </p>
      </div>

      <div className="flex gap-4 mb-6">
        {renderSummaryCard(portfolios.bist, "bist")}
        {renderSummaryCard(portfolios.us, "us")}
        {renderSummaryCard(portfolios.crypto, "crypto")}
      </div>

      {error && (
        <div className="rounded-sm px-4 py-2 font-mono text-xs mb-4" style={{ color: "var(--term-red)" }}>{error}</div>
      )}

      {/* Tab selector */}
      <div className="flex gap-1 mb-4">
        {(["bist", "us", "crypto"] as PortfolioSlug[]).map((slug) => (
          <button key={slug} onClick={() => setActiveTab(slug)}
            className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none"
            style={{ border: "1px solid var(--term-border)", backgroundColor: activeTab === slug ? "var(--term-border)" : "var(--term-bg)",
              color: activeTab === slug ? PORTFOLIO_ACCENTS[slug] : "var(--term-muted)" }}>
            {PORTFOLIO_ICONS[slug]} {slug === "bist" ? "BIST DETAY" : slug === "us" ? "US DETAY" : "KRİPTO DETAY"}
          </button>
        ))}
      </div>

      {/* ── KRİPTO SEKME: M5 mum grafiği + analiz ── */}
      {activeTab === "crypto" && (
        <>
          <div className="rounded-sm p-4 mb-4" style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}>
            <div className="flex items-center justify-between mb-3">
              <div className="font-mono text-xs tracking-wider" style={{ color: "var(--term-muted)" }}>
                BTCUSDT M5 MUM GRAFİĞİ <span className="text-[9px]">(anlık, 30s güncelleme)</span>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={cryptoChartSymbol}
                  onChange={(e) => setCryptoChartSymbol(e.target.value)}
                  className="font-mono text-[11px] px-2 py-1 rounded-sm bg-transparent"
                  style={{ border: "1px solid var(--term-border)", color: "var(--term-text)" }}
                >
                  {cryptoUniverse.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                {cryptoLoading && <span className="text-[10px] font-mono" style={{ color: "var(--term-muted)" }}>…</span>}
              </div>
            </div>

            {cryptoKlines.length > 0 ? (
              <CryptoChart klines={cryptoKlines} height={340} />
            ) : (
              <div className="py-16 text-center font-mono text-xs" style={{ color: "var(--term-muted)" }}>
                Grafik yükleniyor…
              </div>
            )}

            {cryptoAnalysis && (
              <div className="flex gap-4 mt-3 flex-wrap">
                <div className="font-mono text-[11px]">
                  <span style={{ color: "var(--term-muted)" }}>COMPOSITE </span>
                  <span style={{ color: accent }}>{cryptoAnalysis.composite?.toFixed(1) ?? "—"}/100</span>
                </div>
                <div className="font-mono text-[11px]">
                  <span style={{ color: "var(--term-muted)" }}>RSI(5m) </span>
                  <span style={{ color: "var(--term-text)" }}>{cryptoAnalysis.rsi?.toFixed(1) ?? "—"}</span>
                </div>
                <div className="font-mono text-[11px]">
                  <span style={{ color: "var(--term-muted)" }}>MOMENTUM </span>
                  <span style={{ color: "var(--term-text)" }}>{cryptoAnalysis.momentum_score?.toFixed(1) ?? "—"}</span>
                </div>
                <div className="font-mono text-[11px]">
                  <span style={{ color: "var(--term-muted)" }}>SİNYAL </span>
                  <span style={{ color: cryptoAnalysis.signal === "bullish" ? "var(--term-green)" : cryptoAnalysis.signal === "bearish" ? "var(--term-red)" : "var(--term-muted)" }}>
                    {cryptoAnalysis.signal?.toUpperCase() ?? "—"}
                  </span>
                </div>
                {cryptoAnalysis.volatility_penalty ? (
                  <div className="font-mono text-[11px]">
                    <span style={{ color: "var(--term-muted)" }}>VOL CEZASI </span>
                    <span style={{ color: "var(--term-amber)" }}>{(cryptoAnalysis.volatility_penalty * 100).toFixed(0)}%</span>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </>
      )}

      {!activePortfolio ? (
        <div className="rounded-sm p-8 text-center font-mono text-xs" style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)", color: "var(--term-muted)" }}>
          Yükleniyor…
        </div>
      ) : (
        <>
          <div className="rounded-sm px-4 py-3" style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}>
            <div className="grid grid-cols-5 gap-3 text-center">
              <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>NAKİT</div>
                <div className="font-mono text-lg font-semibold" style={{ color: "var(--term-text)" }}>{detSym}{(activePortfolio.cash ?? 0).toFixed(2)}</div></div>
              <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>MALİYET</div>
                <div className="font-mono text-lg font-semibold" style={{ color: "var(--term-text)" }}>{detSym}{(activePortfolio.total_cost ?? 0).toFixed(2)}</div></div>
              <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>PİYASA DEĞERİ</div>
                <div className="font-mono text-lg font-semibold" style={{ color: "var(--term-text)" }}>{detSym}{(activePortfolio.total_market_value ?? 0).toFixed(2)}</div></div>
              <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>P/L</div>
                <div className="font-mono text-lg font-semibold" style={{ color: (activePortfolio.total_pl ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                  {(activePortfolio.total_pl ?? 0) >= 0 ? "+" : ""}{detSym}{(activePortfolio.total_pl ?? 0).toFixed(2)}</div></div>
              <div><div className="text-[10px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>P/L %</div>
                <div className="font-mono text-lg font-semibold" style={{ color: (activePortfolio.total_pl_pct ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                  {(activePortfolio.total_pl_pct ?? 0).toFixed(1)}%</div></div>
            </div>
          </div>

          {/* AÇIK POZİSYONLAR */}
          {activePortfolio.positions.length > 0 ? (
            <div className="rounded-sm mt-4" style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}>
              <div className="px-4 py-3 text-xs font-mono tracking-wider" style={{ color: "var(--term-muted)", borderBottom: `1px solid ${borderColor}` }}>
                AÇIK POZİSYONLAR ({activePortfolio.positions.length})
              </div>
              {activePortfolio.positions.map((pos) => {
                const chg = pos.change_pct ?? 0;
                const chgColor = chg > 0 ? "var(--term-green)" : chg < 0 ? "var(--term-red)" : "var(--term-muted)";
                const chgSign = chg > 0 ? "▲" : chg < 0 ? "▼" : "";
                return (
                  <div key={pos.id} className="flex items-center justify-between px-4 py-3 font-mono text-xs" style={{ borderTop: `1px solid ${borderColor}` }}>
                    <div>
                      <span className="font-semibold" style={{ color: chgColor }}>{pos.ticker}</span>
                      <span style={{ color: chgColor, marginLeft: 4, fontSize: "10px" }}>
                        {chgSign}{Math.abs(chg).toFixed(2)}%
                      </span>
                      <span style={{ color: "var(--term-muted)" }}> x{pos.quantity} @ {detSym}{pos.entry_price.toFixed(4)}</span>
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
          ) : (
            <div className="rounded-sm mt-4 px-4 py-6 text-center font-mono text-xs" style={{ border: `1px dashed ${borderColor}`, color: "var(--term-muted)" }}>
              {activeTab === "crypto" ? "Açık kripto pozisyonu yok. ▶ ÇALIŞTIR ile M5 tarama başlat." : "Açık pozisyon yok."}
            </div>
          )}

          {/* SON KARARLAR */}
          {decisions.length > 0 && (
            <div className="rounded-sm mt-4" style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}>
              <div className="px-4 py-3 text-xs font-mono tracking-wider" style={{ color: "var(--term-muted)", borderBottom: `1px solid ${borderColor}` }}>
                SON KARARLAR
              </div>
              {decisions.slice(0, 6).map((d) => (
                <div key={d.id} className="flex items-center justify-between px-4 py-2 font-mono text-[11px]" style={{ borderTop: `1px solid ${borderColor}` }}>
                  <div><span className="font-semibold" style={{ color: d.action === "buy" ? "var(--term-green)" : "var(--term-red)" }}>
                    {d.action === "buy" ? "AL" : "SAT"} {d.ticker}</span>
                    <span style={{ color: "var(--term-muted)" }}> x{d.quantity} @ {detSym}{d.price.toFixed(4)}</span>
                  </div>
                  <div className="text-right max-w-[220px] truncate" style={{ color: "var(--term-muted)" }}>{d.reasoning.slice(0, 40)}…</div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <div className="flex gap-3 mt-6">
        {(["bist", "us", "crypto"] as PortfolioSlug[]).map((slug) => (
          <button key={slug} onClick={() => handleRun(slug)} disabled={running}
            className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none disabled:opacity-40"
            style={{ border: `1px solid ${PORTFOLIO_ACCENTS[slug]}`, color: PORTFOLIO_ACCENTS[slug] }}>
            ▶ {slug === "bist" ? "BIST" : slug === "us" ? "US" : "KRİPTO"} AJANI ÇALIŞTIR
          </button>
        ))}
      </div>

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
              <div className="font-mono text-sm" style={{ color: "var(--term-amber)" }}>📋 TRADE GEÇMİŞİ — {PORTFOLIO_LABELS[activeTab].toUpperCase()}</div>
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
                        <td className="px-2 py-1.5 text-right">{detSym}{d.price.toFixed(4)}</td>
                        <td className="px-2 py-1.5 text-right">{detSym}{d.total_amount.toFixed(2)}</td>
                        <td className="px-2 py-1.5 text-right" style={{ color: pl != null ? (pl >= 0 ? "var(--term-green)" : "var(--term-red)") : "var(--term-muted)" }}>
                          {pl != null ? `${pl >= 0 ? "+" : ""}${detSym}${pl.toFixed(2)}` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                  {decisions.length === 0 && (
                    <tr><td colSpan={7} className="text-center py-6" style={{ color: "var(--term-muted)" }}>İşlem geçmişi yok</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
