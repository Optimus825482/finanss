"use client";

import { useEffect, useState, useCallback } from "react";
import {
  api,
  PipelineStatus,
  Report,
  ReportListItem,
} from "./lib/api";
import { useLivePrices } from "./hooks/useLivePrices";
import SignalChain from "./components/SignalChain";
import StockCard from "./components/StockCard";
import WatchlistBar from "./components/WatchlistBar";
import PortfolioStatusBar from "./components/PortfolioStatusBar";
import ErrorBoundary from "./components/ErrorBoundary";

export default function Dashboard() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [history, setHistory] = useState<ReportListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [portfolioSlug, setPortfolioSlug] = useState<"bist" | "us">("bist");

  // Live prices via SSE
  const { watchlist, portfolio, error: liveError } =
    useLivePrices(portfolioSlug);

  const refreshStatus = useCallback(async () => {
    try {
      const s = await api.getStatus();
      setStatus(s);
      return s;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Bilinmeyen hata";
      setError(
        `Backend'e bağlanılamadı: ${msg}. http://localhost:8012 çalışıyor mu?`
      );
      return null;
    }
  }, []);

  const refreshReport = useCallback(async () => {
    try {
      const r = await api.getLatestReport();
      setReport(r);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Bilinmeyen hata";
      if (!msg.includes("404")) setError(`Rapor alınamadı: ${msg}`);
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const h = await api.getHistory();
      setHistory(h);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Bilinmeyen hata";
      setError(`Geçmiş yüklenemedi: ${msg}`);
    }
  }, []);

  // Initial loading — only status/report/history (SSE is independent)
  useEffect(() => {
    Promise.all([refreshStatus(), refreshReport(), refreshHistory()]).finally(
      () => setInitialLoading(false)
    );
  }, [refreshStatus, refreshReport, refreshHistory]);

  // Poll status while pipeline is running
  useEffect(() => {
    if (!status?.running) return;
    const interval = setInterval(async () => {
      const s = await refreshStatus();
      if (s && !s.running) {
        refreshReport();
        refreshHistory();
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [status?.running, refreshStatus, refreshReport, refreshHistory]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      await api.generate();
      await refreshStatus();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Bilinmeyen hata";
      setError(`Rapor başlatılamadı: ${msg}`);
    } finally {
      setGenerating(false);
    }
  };

  const loadReport = async (id: number) => {
    try {
      const r = await api.getReport(id);
      setReport(r);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Bilinmeyen hata";
      setError(`Rapor yüklenemedi: ${msg}`);
    }
  };

  return (
    <ErrorBoundary>
      <main className="min-h-screen px-6 py-6 max-w-6xl mx-auto">
        {/* ========== CANLI BÖLÜM — SSE ========== */}
        <WatchlistBar items={watchlist} />

        <PortfolioStatusBar
          portfolio={portfolio}
          slug={portfolioSlug}
          onToggle={setPortfolioSlug}
        />

        {liveError && (
          <div
            className="text-xs px-4 py-2 rounded-sm mb-4 font-mono"
            style={{
              backgroundColor: "rgba(220, 38, 38, 0.1)",
              color: "var(--term-red)",
              border: "1px solid var(--term-red)",
            }}
          >
            {liveError}
          </div>
        )}

        {/* ========== RAPOR BÖLÜMÜ ========== */}

        {/* Rapor üret button bar */}
        <div
          className="scanline rounded-sm px-4 py-3 mb-4 flex items-center justify-between"
          style={{
            backgroundColor: "var(--term-panel)",
            border: "1px solid var(--term-border)",
          }}
        >
          <div>
            <div
              className="font-mono text-[11px] tracking-[0.2em]"
              style={{ color: "var(--term-amber)" }}
            >
              ORBIS FINANCE ANALYZE TEAM
            </div>
            <p className="text-xs mt-0.5" style={{ color: "var(--term-muted)" }}>
              {report
                ? new Date(report.created_at).toLocaleString("tr-TR")
                : "henüz rapor yok"}
            </p>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating || status?.running}
            className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              border: "1px solid var(--term-amber)",
              color: "var(--term-amber)",
            }}
          >
            {status?.running ? "PIPELINE ÇALIŞIYOR…" : "▶ RAPORU ŞİMDİ ÜRET"}
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div
            className="text-sm px-4 py-3 rounded-sm mb-4 font-mono"
            style={{
              backgroundColor: "rgba(220, 38, 38, 0.1)",
              color: "var(--term-red)",
              border: "1px solid var(--term-red)",
            }}
          >
            {error}
          </div>
        )}

        {/* Initial loading */}
        {initialLoading && !error && (
          <div
            className="mb-4 rounded-sm p-8 text-center font-mono text-sm"
            style={{
              color: "var(--term-muted)",
              border: "1px dashed var(--term-border)",
            }}
          >
            Veriler yükleniyor…
          </div>
        )}

        {/* Signal chain */}
        {!initialLoading && status && (
          <div className="mb-4">
            <SignalChain agents={status.agents} />
          </div>
        )}

        {/* Report grid + history sidebar */}
        {!initialLoading && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3 space-y-6">
              {report && (
                <div
                  className="rounded-sm p-4"
                  style={{
                    backgroundColor: "var(--term-panel)",
                    border: "1px solid var(--term-border)",
                  }}
                >
                  <div
                    className="text-[11px] tracking-[0.2em] font-mono mb-2"
                    style={{ color: "var(--term-muted)" }}
                  >
                    GÜNLÜK ÖZET
                  </div>
                  <p
                    className="text-sm leading-relaxed"
                    style={{ color: "var(--term-text)" }}
                  >
                    {report.summary}
                  </p>
                  <div
                    className="text-[10px] font-mono mt-2"
                    style={{ color: "var(--term-muted)" }}
                  >
                    {report.candidates_scanned} sembol tarandı ·{" "}
                    {report.picks.length} öneri
                  </div>
                </div>
              )}

              {report && report.picks.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {report.picks.map((pick, idx) => (
                    <StockCard
                      key={pick.ticker}
                      pick={pick}
                      rank={idx + 1}
                      showPredict={false}
                    />
                  ))}
                </div>
              ) : (
                !status?.running &&
                !initialLoading && (
                  <div
                    className="border border-dashed rounded-sm p-10 text-center font-mono text-sm"
                    style={{
                      borderColor: "var(--term-border)",
                      color: "var(--term-muted)",
                    }}
                  >
                    Henüz rapor üretilmedi. &quot;RAPORU ŞİMDİ ÜRET&quot; ile ilk taramayı
                    başlat.
                  </div>
                )
              )}
            </div>

            <div className="lg:col-span-1">
              <div
                className="rounded-sm p-4 sticky top-20"
                style={{
                  backgroundColor: "var(--term-panel)",
                  border: "1px solid var(--term-border)",
                }}
              >
                <div
                  className="text-[11px] tracking-[0.2em] font-mono mb-3"
                  style={{ color: "var(--term-muted)" }}
                >
                  RAPOR GEÇMİŞİ
                </div>
                <div className="space-y-1">
                  {history.length === 0 && (
                    <div
                      className="text-xs font-mono"
                      style={{ color: "var(--term-muted)" }}
                    >
                      Kayıt yok
                    </div>
                  )}
                  {history.map((h) => (
                    <button
                      key={h.id}
                      onClick={() => loadReport(h.id)}
                      className="w-full text-left px-2 py-2 rounded-sm font-mono text-xs transition-none"
                      style={{
                        backgroundColor:
                          report?.id === h.id
                            ? "var(--term-border)"
                            : "transparent",
                        color:
                          report?.id === h.id
                            ? "var(--term-amber)"
                            : "var(--term-text)",
                      }}
                    >
                      <div>
                        {new Date(h.created_at).toLocaleDateString("tr-TR")}
                      </div>
                      <div style={{ color: "var(--term-muted)" }}>
                        {h.top_ticker || "—"} · {h.candidates_scanned} sembol
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </ErrorBoundary>
  );
}
