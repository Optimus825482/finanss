"use client";

import { useEffect, useState, useRef } from "react";
import { api, ReportListItem, Report } from "../lib/api";
import StockCard from "../components/StockCard";
import Loader from "../components/Loader";

export default function RaporlarPage() {
  const [history, setHistory] = useState<ReportListItem[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exchangeFilter, setExchangeFilter] = useState<string | null>(null); // null=tum, "BIST", "US"
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.getHistory(exchangeFilter || undefined).then(setHistory).catch(() => {});
  }, [exchangeFilter]);

  useEffect(() => {
    api.markAllNotificationsRead().catch(() => {});
  }, []);

  // Cleanup poll on unmount
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleGenerate = async (exchange?: string) => {
    const label = exchange || "TÜM";
    setGenerating(label);
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    try {
      await api.generate(exchange);
      _startPoll();
    } catch {
      setGenerating(null);
    }
  };

  const handleGenerateDeep = async (exchange?: string) => {
    const label = exchange ? `${exchange} (DERIN)` : "TÜM (DERIN)";
    setGenerating(label);
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    try {
      await api.generateDeep(exchange);
      _startPoll();
    } catch {
      setGenerating(null);
    }
  };

  // Poll generator helper
  const _startPoll = () => {
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.getStatus();
        if (!s.running) {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          const h = await api.getHistory();
          setHistory(h);
          if (h.length > 0) loadReport(h[0].id);
          setGenerating(null);
        }
      } catch { clearInterval(pollRef.current!); pollRef.current = null; setGenerating(null); }
    }, 2000);
  };

  const loadReport = async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.getReport(id);
      setReport(r);
      try { await api.markReportNotificationsRead(id); } catch {}
    } catch(e) {
      setError("Rapor yüklenemedi: " + (e instanceof Error ? e.message : "Beklenmeyen hata"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen px-6 py-8 max-w-6xl mx-auto">
      <div
        className="rounded-sm px-6 py-4 mb-6"
        style={{
          backgroundColor: "var(--term-panel)",
          border: "1px solid var(--term-border)",
        }}
      >
        <h1 className="font-mono text-xl font-semibold mb-1" style={{ color: "var(--term-text)" }}>
          RAPORLAR
        </h1>
        <p className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>
          Geçmiş araştırma raporlarını görüntüle, detaylı analizleri incele
        </p>
      </div>

      {/* Üret butonları */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <button
          onClick={() => handleGenerate()}
          disabled={generating !== null}
          className="px-4 py-2 font-mono text-xs rounded-sm transition-none disabled:opacity-40"
          style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}
        >
          {generating === "TÜM" ? "ÜRETİLİYOR…" : "📊 TÜM EVREN"}
        </button>
        <button
          onClick={() => handleGenerate("BIST")}
          disabled={generating !== null}
          className="px-4 py-2 font-mono text-xs rounded-sm transition-none disabled:opacity-40"
          style={{ border: "1px solid var(--term-green)", color: "var(--term-green)" }}
        >
          {generating === "BIST" ? "ÜRETİLİYOR…" : "🇹🇷 BIST"}
        </button>
        <button
          onClick={() => handleGenerate("NASDAQ")}
          disabled={generating !== null}
          className="px-4 py-2 font-mono text-xs rounded-sm transition-none disabled:opacity-40"
          style={{ border: "1px solid #3b82f6", color: "#3b82f6" }}
        >
          {generating === "NASDAQ" ? "ÜRETİLİYOR…" : "🇺🇸 NASDAQ"}
        </button>
        <button
          onClick={() => handleGenerateDeep()}
          disabled={generating !== null}
          className="px-4 py-2 font-mono text-xs rounded-sm transition-none disabled:opacity-40"
          style={{ border: "1px solid #a855f7", color: "#a855f7" }}
        >
          {generating === "TÜM (DERIN)" ? "ÜRETİLİYOR…" : "🔬 DERİN"}
        </button>
      </div>

      {/* Exchange filtresi */}
      <div className="flex gap-2 mb-4">
        {[
          { label: "TÜMÜ", value: null },
          { label: "🇹🇷 BIST", value: "BIST" },
          { label: "🇺🇸 US", value: "US" },
        ].map((f) => (
          <button key={f.label}
            onClick={() => setExchangeFilter(f.value)}
            className="font-mono text-[10px] px-3 py-1 rounded-sm transition-none"
            style={{
              border: "1px solid var(--term-border)",
              backgroundColor: exchangeFilter === f.value ? "rgba(230,160,0,0.15)" : "transparent",
              color: exchangeFilter === f.value ? "var(--term-amber)" : "var(--term-muted)",
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Rapor listesi */}
        <div className="lg:col-span-1">
          <div
            className="rounded-sm p-4"
            style={{
              backgroundColor: "var(--term-panel)",
              border: "1px solid var(--term-border)",
            }}
          >
            <div
              className="text-[11px] tracking-[0.2em] font-mono mb-3"
              style={{ color: "var(--term-muted)" }}
            >
              TÜM RAPORLAR
            </div>
            <div className="space-y-1">
              {history.length === 0 && (
                <div className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>
                  Henüz rapor yok
                </div>
              )}
              {history.map((h) => (
                <button
                  key={h.id}
                  onClick={() => loadReport(h.id)}
                  disabled={loading}
                  className="w-full text-left px-2 py-2 rounded-sm font-mono text-xs transition-none flex justify-between items-start disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{
                    backgroundColor:
                      report?.id === h.id ? "var(--term-border)" : "transparent",
                    color:
                      report?.id === h.id ? "var(--term-amber)" : "var(--term-text)",
                  }}
                >
                  <div>
                    <div>{new Date(h.created_at).toLocaleDateString("tr-TR")}</div>
                    <div className="text-[10px]" style={{ color: "var(--term-muted)" }}>
                      {new Date(h.created_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
                    </div>
                    <div style={{ color: "var(--term-muted)" }}>
                      {h.top_ticker || "—"} · {h.candidates_scanned} sembol
                    </div>
                  </div>
                  <span onClick={(e) => { e.stopPropagation(); api.deleteReport(h.id).then(() => { setHistory(prev => prev.filter(x => x.id !== h.id)); if (report?.id === h.id) setReport(null); }); }}
                    className="text-term-red text-[10px] transition-none shrink-0 mt-0.5" aria-label="Raporu sil">✕</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Rapor detayı */}
        <div className="lg:col-span-3">
          {loading && (<Loader />)}
          {error && !loading && (
            <div className="rounded-sm p-4 text-center" style={{ border: "1px solid var(--term-red)", backgroundColor: "var(--term-panel)" }}>
              <div className="text-sm font-mono" style={{ color: "var(--term-red)" }}>{error}</div>
            </div>
          )}
          {!report && !loading && !error && (
            <div
              className="rounded-sm p-12 text-center"
              style={{
                border: "1px dashed var(--term-border)",
                backgroundColor: "var(--term-panel)",
              }}
            >
              <div className="text-sm font-mono" style={{ color: "var(--term-muted)" }}>
                Görüntülemek için bir rapor seç
              </div>
            </div>
          )}
          {report && !loading && (
            <div className="space-y-6">
              <div
                className="rounded-sm p-4"
                style={{
                  backgroundColor: "var(--term-panel)",
                  border: "1px solid var(--term-border)",
                }}
              >
                <div
                  className="text-xs font-mono tracking-wider mb-2"
                  style={{ color: "var(--term-muted)" }}
                >
                  {new Date(report.created_at).toLocaleString("tr-TR")} · {report.candidates_scanned} sembol tarandı ·{" "}
                  {report.picks.length} öneri
                </div>
                <h2 className="font-mono text-lg font-semibold mb-2" style={{ color: "var(--term-text)" }}>
                  Günlük Özet
                </h2>
                <p className="text-sm leading-relaxed" style={{ color: "var(--term-text)" }}>
                  {report.summary}
                </p>
              </div>

              {report.picks.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {report.picks.map((pick, idx) => (
                    <StockCard key={pick.ticker} pick={pick} rank={idx + 1} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
