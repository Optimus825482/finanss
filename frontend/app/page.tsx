"use client";

import { useEffect, useState, useCallback } from "react";
import { api, PipelineStatus, Report, ReportListItem } from "./lib/api";
import SignalChain from "./components/SignalChain";
import StockCard from "./components/StockCard";
import WatchlistPanel from "./components/WatchlistPanel";
import PortfolioPanel from "./components/PortfolioPanel";

export default function Dashboard() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [history, setHistory] = useState<ReportListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      const s = await api.getStatus();
      setStatus(s);
      return s;
    } catch (e) {
      setError("Backend'e bağlanılamadı. http://localhost:8000 çalışıyor mu?");
      return null;
    }
  }, []);

  const refreshReport = useCallback(async () => {
    try {
      const r = await api.getLatestReport();
      setReport(r);
      setError(null);
    } catch {
      // henüz rapor yoksa sessiz geç
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const h = await api.getHistory();
      setHistory(h);
    } catch {
      // yoksay
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    refreshReport();
    refreshHistory();
  }, [refreshStatus, refreshReport, refreshHistory]);

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
    try {
      await api.generate();
      await refreshStatus();
    } catch {
      setError("Rapor başlatılamadı.");
    } finally {
      setGenerating(false);
    }
  };

  const loadReport = async (id: number) => {
    const r = await api.getReport(id);
    setReport(r);
  };

  return (
    <main className="min-h-screen bg-term-bg px-6 py-8 max-w-6xl mx-auto">
      {/* Hero */}
      <div className="scanline border border-term-border bg-term-panel rounded-sm px-6 py-5 mb-6 flex items-center justify-between">
        <div>
          <div className="font-mono text-[11px] tracking-[0.25em] text-term-amber mb-1">
            ARAŞTIRMA MASASI · CANLI
          </div>
          <h1 className="font-mono text-2xl font-semibold text-term-text">
            Uluslararası Hisse Araştırma Ekibi
          </h1>
          <p className="text-sm text-term-muted mt-1">
            5 ajan · günlük otomatik tarama · {report ? new Date(report.created_at).toLocaleString("tr-TR") : "henüz rapor yok"}
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating || status?.running}
          className="font-mono text-xs tracking-wider px-5 py-3 border border-term-amber text-term-amber rounded-sm hover:bg-term-amber hover:text-term-bg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {status?.running ? "PIPELINE ÇALIŞIYOR…" : "▶ RAPORU ŞİMDİ ÜRET"}
        </button>
      </div>

      {error && (
        <div className="border border-term-red/40 bg-term-red/10 text-term-red text-sm px-4 py-3 rounded-sm mb-6 font-mono">
          {error}
        </div>
      )}

      {/* Sinyal zinciri */}
      {status && (
        <div className="mb-6">
          <SignalChain agents={status.agents} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Ana içerik */}
        <div className="lg:col-span-3 space-y-6">
          {report && (
            <div className="border border-term-border bg-term-panel rounded-sm p-4">
              <div className="text-[11px] tracking-[0.2em] text-term-muted font-mono mb-2">
                GÜNLÜK ÖZET
              </div>
              <p className="text-sm text-term-text leading-relaxed">{report.summary}</p>
              <div className="text-[10px] font-mono text-term-muted mt-2">
                {report.candidates_scanned} sembol tarandı · {report.picks.length} öneri
              </div>
            </div>
          )}

          {report && report.picks.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {report.picks.map((pick, idx) => (
                <StockCard key={pick.ticker} pick={pick} rank={idx + 1} />
              ))}
            </div>
          ) : (
            !status?.running && (
              <div className="border border-dashed border-term-border rounded-sm p-10 text-center text-term-muted font-mono text-sm">
                Henüz rapor üretilmedi. "RAPORU ŞİMDİ ÜRET" ile ilk taramayı başlat.
              </div>
            )
          )}
        </div>

        {/* Geçmiş */}
        <div className="lg:col-span-1">
          <div className="border border-term-border bg-term-panel rounded-sm p-4 sticky top-6">
            <div className="text-[11px] tracking-[0.2em] text-term-muted font-mono mb-3">
              RAPOR GEÇMİŞİ
            </div>
            <div className="space-y-1">
              {history.length === 0 && (
                <div className="text-xs text-term-muted font-mono">Kayıt yok</div>
              )}
              {history.map((h) => (
                <button
                  key={h.id}
                  onClick={() => loadReport(h.id)}
                  className={`w-full text-left px-2 py-2 rounded-sm font-mono text-xs hover:bg-term-border/50 transition-colors ${
                    report?.id === h.id ? "bg-term-border/70 text-term-amber" : "text-term-text"
                  }`}
                >
                  <div>{new Date(h.created_at).toLocaleDateString("tr-TR")}</div>
                  <div className="text-term-muted">
                    {h.top_ticker || "—"} · {h.candidates_scanned} sembol
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <WatchlistPanel />
        <PortfolioPanel />
      </div>
    </main>
  );
}
