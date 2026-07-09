"use client";

import { useEffect, useState } from "react";
import { api, Report, ReportListItem, AgentPortfolio, AgentDecision, PipelineStatus } from "../lib/api";
import Loader from "../components/Loader";

export default function BistPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [history, setHistory] = useState<ReportListItem[]>([]);
  const [portfolio, setPortfolio] = useState<AgentPortfolio | null>(null);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string[]>([]);

  const load = async () => {
    try { setPortfolio(await api.getAgentPortfolio()); } catch { /* */ }
    try { setDecisions(await api.getAgentDecisions(10)); } catch { /* */ }
    try {
      const s = await api.getStatus();
      setGenerating(s.running);
      if (s.running && s.progress) setProgress(s.progress);
    } catch { /* */ }
    try {
      const h = await api.getHistory();
      setHistory(h);
      const bistReports = h.filter(r => r.candidates_scanned >= 40 && r.candidates_scanned <= 100);
      if (bistReports.length > 0) {
        const r = await api.getReport(bistReports[0].id);
        setReport(r);
      }
    } catch { /* */ }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => { const i = setInterval(load, 3000); return () => clearInterval(i); }, []);
  // Clear progress when pipeline finishes
  useEffect(() => { if (!generating) setProgress([]); }, [generating]);

  const handleGenerate = async () => {
    setError(null);
    try {
      await api.generate("BIST");
    } catch {
      setError("Rapor üretilemedi");
    }
  };

  const borderColor = "var(--term-border)";
  const bistPicks = report?.picks?.filter(p =>
    p.ticker.endsWith(".IS")
  ) ?? [];

  return (
    <main className="min-h-screen px-6 py-8 max-w-6xl mx-auto">
      {/* Header */}
      <div
        className="rounded-sm px-6 py-4 mb-6"
        style={{ backgroundColor: "var(--term-panel)", border: `1px solid ${borderColor}` }}
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-mono text-xl font-semibold" style={{ color: "var(--term-text)" }}>
              🇹🇷 BİST
            </h1>
            <p className="text-xs font-mono mt-1" style={{ color: "var(--term-muted)" }}>
              Borsa İstanbul — otomatik tarama, analiz ve portföy yönetimi
            </p>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="px-4 py-2 font-mono text-xs rounded-sm transition-none disabled:opacity-40 whitespace-nowrap"
            style={{ border: "1px solid var(--term-green)", color: "var(--term-green)" }}
          >
            {generating ? "TARANIYOR…" : "🔍 BIST TARA"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-sm px-4 py-2 font-mono text-xs" style={{ border: `1px solid var(--term-red)`, color: "var(--term-red)" }}>
          {error}
        </div>
      )}

      {/* Canli ilerleme */}
      {generating && progress.length > 0 && (
        <div className="mb-4 rounded-sm px-4 py-3 font-mono text-xs"
          style={{ backgroundColor: "var(--term-panel)", border: "1px solid var(--term-amber)" }}>
          <div className="text-[10px] tracking-wider mb-1" style={{ color: "var(--term-amber)" }}>
            🔄 PIPELINE ÇALIŞIYOR
          </div>
          {progress.map((msg, i) => (
            <div key={i} className="py-0.5" style={{ color: i === progress.length - 1 ? "var(--term-text)" : "var(--term-muted)" }}>
              {i === progress.length - 1 ? "▶" : "✓"} {msg}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ajan portföy özeti */}
        <div className="lg:col-span-1">
          <div
            className="rounded-sm p-4"
            style={{ backgroundColor: "var(--term-panel)", border: `1px solid ${borderColor}` }}
          >
            <div className="text-[11px] tracking-[0.2em] font-mono mb-3" style={{ color: "var(--term-muted)" }}>
              🤖 AJAN PORTFÖYÜ
            </div>
            {!portfolio ? (
              <div className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>Yükleniyor…</div>
            ) : (
              <>
                <div className="space-y-2 mb-4">
                  <div className="flex justify-between font-mono text-xs">
                    <span style={{ color: "var(--term-muted)" }}>Nakit</span>
                    <span style={{ color: "var(--term-text)" }}>${portfolio.cash.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between font-mono text-xs">
                    <span style={{ color: "var(--term-muted)" }}>Pozisyon</span>
                    <span style={{ color: "var(--term-text)" }}>{portfolio.position_count}</span>
                  </div>
                  <div className="flex justify-between font-mono text-xs">
                    <span style={{ color: "var(--term-muted)" }}>Piyasa Değeri</span>
                    <span style={{ color: "var(--term-text)" }}>${portfolio.total_market_value.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between font-mono text-xs">
                    <span style={{ color: "var(--term-muted)" }}>P/L</span>
                    <span style={{ color: portfolio.total_pl >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                      {portfolio.total_pl >= 0 ? "+" : ""}${portfolio.total_pl.toFixed(2)}
                    </span>
                  </div>
                </div>

                {portfolio.positions.length > 0 && (
                  <div>
                    <div className="text-[10px] font-mono tracking-wider mb-1" style={{ color: "var(--term-muted)" }}>
                      POZİSYONLAR
                    </div>
                    {portfolio.positions.map(p => (
                      <div key={p.id} className="flex justify-between font-mono text-[11px] py-1"
                        style={{ borderTop: `1px solid ${borderColor}` }}>
                        <span style={{ color: "var(--term-text)" }}>{p.ticker}</span>
                        <span style={{ color: p.unrealized_pl >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                          {p.unrealized_pl >= 0 ? "+" : ""}${p.unrealized_pl.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            <div className="mt-4">
              <div className="text-[10px] font-mono tracking-wider mb-1" style={{ color: "var(--term-muted)" }}>
                SON KARARLAR
              </div>
              {decisions.length === 0 && (
                <div className="text-[10px] font-mono" style={{ color: "var(--term-muted)" }}>Henüz karar yok</div>
              )}
              {decisions.slice(0, 5).map(d => (
                <div key={d.id} className="flex justify-between font-mono text-[10px] py-1"
                  style={{ borderTop: `1px solid ${borderColor}` }}>
                  <span style={{ color: d.action === "buy" ? "var(--term-green)" : "var(--term-red)" }}>
                    {d.action === "buy" ? "AL" : "SAT"} {d.ticker}
                  </span>
                  <span style={{ color: "var(--term-muted)" }}>x{d.quantity}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* BIST pick'leri */}
        <div className="lg:col-span-2">
          <div
            className="rounded-sm"
            style={{ backgroundColor: "var(--term-panel)", border: `1px solid ${borderColor}` }}
          >
            <div className="px-4 py-3 text-[11px] tracking-[0.2em] font-mono" style={{ color: "var(--term-muted)" }}>
              BIST ÖNERİLERİ {report ? `· ${report.candidates_scanned} sembol tarandı` : ""}
            </div>

            {loading && <Loader />}

            {!loading && bistPicks.length === 0 && (
              <div className="px-4 py-10 text-center font-mono text-xs" style={{ color: "var(--term-muted)" }}>
                Henüz BIST raporu yok. "BIST TARA" butonuna basarak ilk taramayı başlat.
              </div>
            )}

            {bistPicks.map((pick, i) => (
              <div
                key={pick.ticker}
                className="px-4 py-3"
                style={{ borderTop: `1px solid ${borderColor}` }}
              >
                <div className="flex items-center justify-between">
                  <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>
                    {pick.ticker.replace(".IS", "")}
                    <span className="text-[10px] ml-2" style={{ color: "var(--term-muted)" }}>
                      #{i + 1}
                    </span>
                  </div>
                  <div className="text-right font-mono text-sm" style={{ color: "var(--term-text)" }}>
                    ${pick.price.toFixed(2)}
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-2 mt-2">
                  <Score label="BİLEŞİK" value={pick.composite_score} />
                  <Score label="TEMEL" value={pick.fundamental_score} />
                  <Score label="SENTİMENT" value={pick.sentiment_score} />
                  <Score label="RİSK" value={pick.risk_score} />
                </div>

                {pick.momentum_pct !== null && (
                  <div className="mt-1 font-mono text-[11px]" style={{ color: pick.momentum_pct >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                  Momentum: {pick.momentum_pct >= 0 ? "+" : ""}{pick.momentum_pct.toFixed(1)}%
                  </div>
                )}

                {pick.narrative && (
                  <div className="mt-1 font-mono text-[11px] leading-relaxed" style={{ color: "var(--term-muted)" }}>
                    {pick.narrative.slice(0, 200)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}

function Score({ label, value }: { label: string; value: number | null }) {
  const v = value ?? 0;
  const color = v >= 70 ? "var(--term-green)" : v >= 50 ? "var(--term-amber)" : "var(--term-red)";
  return (
    <div className="text-center">
      <div className="text-[9px] font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>{label}</div>
      <div className="font-mono text-xs font-semibold" style={{ color }}>{v.toFixed(0)}</div>
    </div>
  );
}
