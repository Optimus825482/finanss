"use client";

import { useState, FormEvent, useEffect, useRef } from "react";
import PriceChart from "./PriceChart";
import {
  api,
  StockAnalysisResult,
  DividendResult,
  RumorScanResult,
  KlineResult,
} from "../lib/api";

type SkillTab = "stock" | "dividend" | "rumors" | "kline";
type Suggestion = { ticker: string; name: string; exchange: string; exchange_name: string; type: string };

const TAB_LABELS: Record<SkillTab, string> = {
  stock: "📊 Hisse Analizi",
  dividend: "💰 Temettü",
  rumors: "📡 Rumor Tara",
  kline: "📈 K-Line",
};

const SIGNAL_TYPE_STYLES: Record<string, React.CSSProperties> = {
  ma: { backgroundColor: "rgba(168,85,247,0.20)", color: "var(--term-text)" },
  insider: { backgroundColor: "rgba(59,130,246,0.20)", color: "var(--term-text)" },
  analyst: { backgroundColor: "rgba(230,160,0,0.20)", color: "var(--term-amber)" },
  regulatory: { backgroundColor: "rgba(249,115,22,0.20)", color: "var(--term-text)" },
  earnings: { backgroundColor: "rgba(107,114,128,0.20)", color: "var(--term-muted)" },
};

export default function SkillPanel() {
  const [tab, setTab] = useState<SkillTab>("stock");
  const [ticker, setTicker] = useState("");
  const [positionStatus, setPositionStatus] = useState<"empty" | "holding">("empty");
  const [positionCost, setPositionCost] = useState("");
  const [positionShares, setPositionShares] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sembol arama autocomplete state
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggLoading, setSuggLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced ticker arama — Yahoo Finance autocomplete
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = ticker.trim();
    if (q.length < 1 || tab === "rumors") {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setSuggLoading(true);
      try {
        const results = await api.suggestTickers(q);
        setSuggestions(results);
        setShowSuggestions(results.length > 0);
      } catch {
        setSuggestions([]);
        setShowSuggestions(false);
      } finally {
        setSuggLoading(false);
      }
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [ticker, tab]);

  const selectSuggestion = (s: Suggestion) => {
    setTicker(s.ticker);
    setShowSuggestions(false);
    setSuggestions([]);
  };

  const [stockResult, setStockResult] = useState<StockAnalysisResult | null>(null);
  const [dividendResult, setDividendResult] = useState<DividendResult | null>(null);
  const [rumorResult, setRumorResult] = useState<RumorScanResult | null>(null);
  const [klineResult, setKlineResult] = useState<KlineResult | null>(null);

  const handleRun = async (e: FormEvent) => {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    if (!t && tab !== "rumors") return;
    setLoading(true);
    setError(null);
    try {
      if (tab === "stock") {
        const position: { status: "empty" | "holding"; cost?: number; shares?: number } =
          positionStatus === "holding" && positionCost && positionShares
            ? {
                status: "holding",
                cost: parseFloat(positionCost),
                shares: parseInt(positionShares),
              }
            : { status: positionStatus };
        setStockResult(await api.analyzeStock(t, position));
      } else if (tab === "dividend") {
        setDividendResult(await api.analyzeDividend(t));
      } else if (tab === "rumors") {
        setRumorResult(await api.scanRumors(t || undefined));
      } else if (tab === "kline") {
        setKlineResult(await api.analyzeKline(t));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Skill çağrısı başarısız");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl p-4 backdrop-blur" style={{ border: "1px solid var(--term-border)", backgroundColor: "var(--term-panel)" }}>
      <div className="mb-4 flex flex-wrap gap-2">
        {(Object.keys(TAB_LABELS) as SkillTab[]).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`rounded-lg px-3 py-1.5 text-sm transition ${
              tab === k
                ? ""
                : "brightness-110"
            }`}
            style={
              tab === k
                ? {
                    backgroundColor: "rgba(230,160,0,0.30)",
                    color: "var(--term-amber)",
                    boxShadow: "0 0 0 1px var(--term-amber)",
                  }
                : {
                    backgroundColor: "rgba(255,255,255,0.05)",
                    color: "var(--term-muted)",
                  }
            }
          >
            {TAB_LABELS[k]}
          </button>
        ))}
      </div>

      <form onSubmit={handleRun} className="mb-4 flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
            className="w-full rounded-lg px-3 py-2 text-sm focus:outline-none"
            style={{
              border: "1px solid var(--term-border)",
              backgroundColor: "var(--term-bg)",
              color: "var(--term-text)",
            }}
            placeholder={tab === "rumors" ? "Ticker veya boş (piyasa geneli)" : "Ticker (örn AAPL)"}
          />
          {suggLoading && (
            <div className="absolute right-3 top-2.5 text-xs" style={{ color: "var(--term-muted)" }}>aranıyor…</div>
          )}
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute z-50 mt-1 w-full rounded-lg shadow-xl max-h-72 overflow-auto" style={{ border: "1px solid var(--term-border)", backgroundColor: "var(--term-panel)" }}>
              {suggestions.map((s) => (
                <button
                  key={`${s.ticker}-${s.exchange}`}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    selectSuggestion(s);
                  }}
                  className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:brightness-110 border-b last:border-0" style={{ borderColor: "var(--term-border)" }}
                >
                  <div className="min-w-0">
                    <span className="font-mono font-semibold" style={{ color: "var(--term-amber)" }}>{s.ticker}</span>
                    <span className="ml-2 truncate text-xs" style={{ color: "var(--term-muted)" }}>{s.name}</span>
                  </div>
                  <span className="shrink-0 rounded px-1.5 py-0.5 text-[10px]" style={{ backgroundColor: "rgba(255,255,255,0.05)", color: "var(--term-muted)" }}>
                    {s.exchange_name || s.exchange}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
        {tab === "stock" && (
          <>
            <select
              value={positionStatus}
              onChange={(e) => setPositionStatus(e.target.value as "empty" | "holding")}
              className="rounded-lg px-2 py-2 text-sm"
              style={{
                border: "1px solid var(--term-border)",
                backgroundColor: "var(--term-bg)",
                color: "var(--term-text)",
              }}
            >
              <option value="empty">Boş pozisyon</option>
              <option value="holding">Pozisyon mevcut</option>
            </select>
            {positionStatus === "holding" && (
              <>
                <input
                  type="number"
                  value={positionCost}
                  onChange={(e) => setPositionCost(e.target.value)}
                  placeholder="Maliyet"
                  className="w-24 rounded-lg px-2 py-2 text-sm"
                  style={{
                    border: "1px solid var(--term-border)",
                    backgroundColor: "var(--term-bg)",
                    color: "var(--term-text)",
                  }}
                />
                <input
                  type="number"
                  value={positionShares}
                  onChange={(e) => setPositionShares(e.target.value)}
                  placeholder="Adet"
                  className="w-20 rounded-lg px-2 py-2 text-sm"
                  style={{
                    border: "1px solid var(--term-border)",
                    backgroundColor: "var(--term-bg)",
                    color: "var(--term-text)",
                  }}
                />
              </>
            )}
          </>
        )}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg px-4 py-2 text-sm font-medium transition hover:brightness-110 disabled:opacity-50"
          style={{
            backgroundColor: "rgba(230,160,0,0.20)",
            color: "var(--term-amber)",
            boxShadow: "0 0 0 1px var(--term-amber)",
          }}
        >
          {loading ? "Çalışıyor..." : "Çalıştır"}
        </button>
      </form>

      {error && (
        <div className="mb-4 rounded-lg px-3 py-2 text-sm" style={{ border: "1px solid rgba(248,113,113,0.30)", backgroundColor: "rgba(248,113,113,0.10)", color: "var(--term-red)" }}>
          {error}
        </div>
      )}

      {/* Stock analysis result — zengin dashboard */}
      {tab === "stock" && stockResult && (
        <div className="space-y-4">
          {/* Üst bar — ticker + conclusion + bias — canlı renk */}
          <div className="flex flex-wrap items-center gap-3 rounded-xl px-4 py-3" style={{ background: "linear-gradient(90deg, var(--term-bg), var(--term-panel))", border: "1px solid var(--term-border)" }}>
            <span className="text-xl font-bold tracking-tight" style={{ color: "var(--term-text)" }}>{stockResult.ticker}</span>
            <span className="rounded-full px-3 py-1 text-xs font-bold tracking-wider uppercase" style={
              stockResult.conclusion === "strong_buy" ? { backgroundColor: "#4ADE80", color: "#12161B" }
              : stockResult.conclusion === "buy" ? { backgroundColor: "rgba(74,222,128,0.80)", color: "var(--term-text)" }
              : stockResult.conclusion === "hold" ? { backgroundColor: "#E6A000", color: "#12161B" }
              : stockResult.conclusion.startsWith("sell") ? { backgroundColor: "#F87171", color: "#12161B" }
              : { backgroundColor: "var(--term-muted)", color: "var(--term-text)" }
            }>
              {stockResult.conclusion.replace(/_/g, " ")}
            </span>
            {stockResult.bias_pct !== null && (
              <span className="rounded-full px-2.5 py-0.5 text-xs font-mono font-bold" style={
                stockResult.bias_pct > 5
                  ? { backgroundColor: "rgba(248,113,113,0.20)", color: "var(--term-red)", border: "1px solid rgba(248,113,113,0.30)" }
                  : stockResult.bias_pct < -5
                  ? { backgroundColor: "rgba(74,222,128,0.20)", color: "var(--term-green)", border: "1px solid rgba(74,222,128,0.30)" }
                  : { backgroundColor: "var(--term-muted)", color: "var(--term-text)", border: "1px solid var(--term-border)" }
              }>
                MA20 {stockResult.bias_pct > 0 ? "+" : ""}{stockResult.bias_pct}%
                {stockResult.bias_pct > 5 && " ⚠ BUY ENGELLENDI"}
              </span>
            )}
          </div>

          {/* Fiyat grafiği */}
          {stockResult.price_history.length > 1 && (
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--term-border)" }}>
              <PriceChart
                data={stockResult.price_history.map(p => ({ date: p.date, open: p.open, high: p.high, low: p.low, close: p.close, volume: p.volume }))}
                color="var(--term-green)"
              />
            </div>
          )}

          {/* Skor card'ları — 4 canlı metrik */}
          <div className="grid grid-cols-4 gap-3">
            {([
              ["Fundamental", stockResult.scores.fundamental, "#06b6d4", "📊"],
              ["Sentiment", stockResult.scores.sentiment, "#a855f7", "💬"],
              ["Risk", stockResult.scores.risk, "#f97316", "⚠️"],
              ["Composite", stockResult.scores.composite, "#22c55e", "⭐"],
            ] as const).map(([label, val, accent, icon]) => {
              const v = val ?? null;
              const hasVal = v !== null && v !== undefined;
              const barColor = hasVal ? (v! >= 60 ? "#22c55e" : v! >= 40 ? "#eab308" : "#ef4444") : "#475569";
              return (
                <div key={label} className="rounded-xl p-3" style={{ border: "1px solid var(--term-border)", backgroundColor: "var(--term-panel)" }}>
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="text-sm">{icon}</span>
                    <span className="text-[11px] font-mono font-semibold tracking-wider uppercase" style={{ color: accent }}>{label}</span>
                  </div>
                  <div className="text-2xl font-bold font-mono mb-1.5" style={{ color: hasVal ? barColor : "#64748b" }}>
                    {hasVal ? v!.toFixed(0) : "—"}
                  </div>
                  {hasVal ? (
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "var(--term-bg)" }}>
                      <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(Math.max(v!, 0), 100)}%`, backgroundColor: barColor }} />
                    </div>
                  ) : (
                    <div className="h-1.5 rounded-full" style={{ backgroundColor: "var(--term-bg)" }} />
                  )}
                  <div className="mt-1 text-[10px] font-mono text-right" style={{ color: barColor }}>
                    {hasVal ? `${v!.toFixed(0)}/100` : "VERİ YOK"}
                  </div>
                </div>
              );
            })}
          </div>

          {/* P/L kartı + İşlem planı — canlı renk */}
          <div className="grid grid-cols-2 gap-3">
            {stockResult.position_pl ? (
              <div className="rounded-xl p-4" style={{ border: "1px solid var(--term-border)", backgroundColor: "var(--term-panel)" }}>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-sm">💰</span>
                  <span className="text-[11px] font-mono font-semibold tracking-wider" style={{ color: "var(--term-amber)" }}>POZISYON P/L</span>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs font-mono">
                    <span style={{ color: "var(--term-muted)" }}>Maliyet</span>
                    <span className="font-semibold" style={{ color: "var(--term-text)" }}>${stockResult.position_pl.cost_total.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-xs font-mono">
                    <span style={{ color: "var(--term-muted)" }}>Güncünlük Değer</span>
                    <span className="font-semibold" style={{ color: "var(--term-text)" }}>${stockResult.position_pl.current_total.toFixed(2)}</span>
                  </div>
                  <div className="pt-2 flex justify-between text-sm font-mono font-bold" style={{ borderTop: "1px solid var(--term-border)" }}>
                    <span style={{ color: "var(--term-muted)" }}>K/Z</span>
                    <span style={{ color: stockResult.position_pl.pl >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                      {stockResult.position_pl.pl >= 0 ? "+" : ""}${stockResult.position_pl.pl.toFixed(2)}
                      <span className="text-xs ml-1">({stockResult.position_pl.pl >= 0 ? "+" : ""}{stockResult.position_pl.pl_pct.toFixed(2)}%)</span>
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-xl p-4 flex items-center justify-center" style={{ border: "1px solid var(--term-border)", backgroundColor: "var(--term-panel)", opacity: 0.5 }}>
                <div className="text-center">
                  <span className="text-2xl block mb-1">💰</span>
                  <span className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>Pozisyon yok</span>
                  <span className="text-[10px] font-mono block mt-0.5" style={{ color: "var(--term-muted)" }}>P/L için pozisyon bilgisi girin</span>
                </div>
              </div>
            )}

            {stockResult.price_history.length > 0 && (() => {
              const last = stockResult.price_history[stockResult.price_history.length - 1]?.close;
              if (last == null) return null;
              const stop = last * 0.92;
              const target = last * 1.10;
              const entryPos = ((last - stop) / (target - stop)) * 100;
              return (
                <div className="rounded-xl p-4" style={{ border: "1px solid var(--term-border)", backgroundColor: "var(--term-panel)" }}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-sm">🎯</span>
                    <span className="text-[11px] font-mono font-semibold tracking-wider" style={{ color: "var(--term-amber)" }}>ISLEM PLANI</span>
                  </div>
                  <div className="space-y-2 mb-3">
                    {[
                      ["Giriş", last, "#22c55e"],
                      ["Stop (-8%)", stop, "#ef4444"],
                      ["Hedef (+10%)", target, "#22c55e"],
                    ].map(([l, v, c]) => (
                      <div key={l as string} className="flex justify-between text-xs font-mono">
                        <span style={{ color: "var(--term-muted)" }}>{l}</span>
                        <span className="font-semibold" style={{ color: c as string }}>${(v as number).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="relative h-4 rounded-full overflow-hidden" style={{ background: "linear-gradient(90deg, #ef4444 0%, #eab308 35%, #22c55e 100%)" }}>
                    <div className="absolute top-0 h-full w-0.5 bg-white shadow-lg" style={{ left: `${entryPos.toFixed(0)}%` }} />
                  </div>
                  <div className="flex justify-between mt-1 text-[10px] font-mono">
                    <span style={{ color: "var(--term-red)" }}>${stop.toFixed(0)}</span>
                    <span className="font-bold" style={{ color: "var(--term-amber)" }}>${last.toFixed(0)}</span>
                    <span style={{ color: "var(--term-green)" }}>${target.toFixed(0)}</span>
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Eksik veri uyarısı */}
          {stockResult.data_missing.length > 0 && (
            <div className="rounded-xl px-4 py-2 flex items-center gap-2" style={{ border: "1px solid rgba(230,160,0,0.30)", backgroundColor: "rgba(230,160,0,0.10)" }}>
              <span className="text-sm">⚠️</span>
              <span className="text-xs font-mono" style={{ color: "var(--term-amber)" }}>Eksik veri: {stockResult.data_missing.join(", ")}</span>
            </div>
          )}

          {/* ═══════════════════════════════════════════════
              DETAILED REPORT — FULL CARD DASHBOARD
              ═══════════════════════════════════════════════ */}
          <div className="rounded-2xl p-5 space-y-5" style={{ border: "1px solid var(--term-border)", backgroundColor: "var(--term-panel)" }}>
            {/* ── Section header ── */}
            <div className="flex items-center gap-2 pb-3" style={{ borderBottom: "1px solid var(--term-border)" }}>
              <span className="text-base">📋</span>
              <span className="text-xs font-mono font-bold tracking-wider uppercase" style={{ color: "var(--term-amber)" }}>Detaylı Rapor</span>
            </div>

            {/* ── Row 1: Tavsiye + Fiyat + MA20 + Pozisyon (4 col) ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                [
                  "Tavsiye",
                  stockResult.conclusion.replace(/_/g, " ").toUpperCase(),
                  stockResult.conclusion.startsWith("strong_buy") ? "#10b981" : stockResult.conclusion === "buy" ? "#059669" : stockResult.conclusion === "hold" ? "#eab308" : "#ef4444",
                  stockResult.conclusion.startsWith("strong_buy") ? "rgba(16,185,129,0.15)" : stockResult.conclusion === "buy" ? "rgba(5,150,105,0.12)" : stockResult.conclusion === "hold" ? "rgba(234,179,8,0.12)" : "rgba(239,68,68,0.12)",
                ],
                [
                  "Güncünlük Fiyat",
                  `$ ${stockResult.price_history[stockResult.price_history.length - 1]?.close?.toFixed(2) ?? "—"}`,
                  "#22d3ee",
                  "rgba(34,211,238,0.12)",
                ],
                [
                  "MA20 Sapma",
                  stockResult.bias_pct !== null ? `${stockResult.bias_pct > 0 ? "+" : ""}${stockResult.bias_pct}%` : "—",
                  stockResult.bias_pct !== null ? (stockResult.bias_pct < -5 ? "#22c55e" : stockResult.bias_pct > 5 ? "#ef4444" : "#eab308") : "#64748b",
                  stockResult.bias_pct !== null ? (stockResult.bias_pct < -5 ? "rgba(34,197,94,0.12)" : stockResult.bias_pct > 5 ? "rgba(239,68,68,0.12)" : "rgba(234,179,8,0.10)") : "rgba(100,116,139,0.08)",
                ],
                [
                  "Pozisyon K/Z",
                  stockResult.position_pl ? `${stockResult.position_pl.pl >= 0 ? "+" : ""}$${stockResult.position_pl.pl.toFixed(0)}` : "Pozisyon Yok",
                  stockResult.position_pl ? (stockResult.position_pl.pl >= 0 ? "#22c55e" : "#ef4444") : "#64748b",
                  stockResult.position_pl ? (stockResult.position_pl.pl >= 0 ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)") : "rgba(100,116,139,0.08)",
                ],
              ].map(([label, value, color, bg]) => (
                <div
                  key={label as string}
                  className="rounded-xl p-4 text-center transition-all"
                  style={{ border: "1px solid var(--term-border)", backgroundColor: bg as string }}
                >
                  <div className="text-[10px] font-mono tracking-wider mb-2 uppercase" style={{ color: "var(--term-muted)" }}>{label}</div>
                  <div className="text-base sm:text-lg font-bold font-mono tracking-tight" style={{ color: color as string }}>
                    {value}
                  </div>
                </div>
              ))}
            </div>

            {/* ── Row 2: Veri Izgarası (4 score cards + 4 veri cards) ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {/* Skor kartları — gradient bar */}
              {([
                ["📊 Fundamental", stockResult.scores.fundamental, "#06b6d4", "rgba(6,182,212,0.10)"],
                ["💬 Sentiment", stockResult.scores.sentiment, "#a855f7", "rgba(168,85,247,0.10)"],
                ["⚠️ Risk", stockResult.scores.risk, "#f97316", "rgba(249,115,22,0.10)"],
                ["⭐ Composite", stockResult.scores.composite, "#22c55e", "rgba(34,197,94,0.10)"],
              ] as const).map(([label, val, accent, bg]) => {
                const v = val ?? null;
                const hasVal = v !== null && v !== undefined;
                const barColor = hasVal ? (v! >= 60 ? "#22c55e" : v! >= 40 ? "#eab308" : "#ef4444") : "#475569";
                return (
                  <div key={label} className="rounded-xl p-4 transition-all" style={{ border: "1px solid var(--term-border)", backgroundColor: bg }}>
                    <div className="text-[10px] font-mono tracking-wider mb-2 uppercase" style={{ color: "var(--term-muted)" }}>{label}</div>
                    <div className="flex items-baseline gap-1 mb-3">
                      <span className="text-2xl font-bold font-mono" style={{ color: hasVal ? barColor : "var(--term-muted)" }}>
                        {hasVal ? v!.toFixed(0) : "—"}
                      </span>
                      <span className="text-[11px] font-mono" style={{ color: "var(--term-muted)" }}>/100</span>
                    </div>
                    {hasVal ? (
                      <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--term-bg)" }}>
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.min(Math.max(v!, 0), 100)}%`,
                            background: `linear-gradient(90deg, ${barColor}88, ${barColor})`,
                          }}
                        />
                      </div>
                    ) : (
                      <div className="h-2 rounded-full" style={{ backgroundColor: "var(--term-bg)" }} />
                    )}
                  </div>
                );
              })}
            </div>

            {/* ── Row 3: PE / Volatilite / Max DD / Momentum ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                ["PE Oranı", stockResult.markdown.match(/PE oranı\s*\|?\s*([\d.]+)/)?.[1] || null, "#06b6d4", "rgba(6,182,212,0.10)", "📈"],
                ["Volatilite (Yıllık)", stockResult.markdown.match(/Volatilite.*?\|?\s*([\d.]+)/)?.[1] || null, "#a855f7", "rgba(168,85,247,0.10)", "📊"],
                ["Max Drawdown", stockResult.markdown.match(/Max drawdown.*?\|?\s*([\d.-]+)/)?.[1] || null, "#f97316", "rgba(249,115,22,0.10)", "📉"],
                ["Momentum", stockResult.markdown.match(/Momentum.*?\|?\s*([\d.-]+)/)?.[1] || null,
                  (() => { const m = stockResult.markdown.match(/Momentum.*?\|?\s*([\d.-]+)/)?.[1]; return m ? (parseFloat(m) > 0 ? "#22c55e" : "#ef4444") : "#64748b"; })(),
                  (() => { const m = stockResult.markdown.match(/Momentum.*?\|?\s*([\d.-]+)/)?.[1]; return m ? (parseFloat(m) > 0 ? "rgba(34,197,94,0.10)" : "rgba(239,68,68,0.10)") : "rgba(100,116,139,0.08)"; })(),
                  "🚀"],
              ].map(([label, val, color, bg, icon]) => (
                <div
                  key={label as string}
                  className="rounded-xl p-4 text-center transition-all"
                  style={{ border: "1px solid var(--term-border)", backgroundColor: bg as string }}
                >
                  <div className="text-lg mb-1">{icon}</div>
                  <div className="text-[10px] font-mono tracking-wider mb-1.5 uppercase" style={{ color: "var(--term-muted)" }}>{label}</div>
                  <div className="text-xl font-bold font-mono" style={{ color: color as string }}>
                    {val ? (label === "PE Oranı" ? val : label === "Volatilite (Yıllık)" ? `%${val}` : label === "Max Drawdown" ? `%${val}` : `%${val}`) : "—"}
                  </div>
                </div>
              ))}
            </div>

            {/* ── Row 4: 🌍 Küresel Makro (8 göstergeli card grid) ── */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-sm">🌍</span>
                <span className="text-[11px] font-mono font-bold tracking-wider uppercase" style={{ color: "var(--term-amber)" }}>Küresel Makro</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {stockResult.macro_indicators?.map((m) => {
                  const ch = m.change_pct;
                  const isUp = ch !== null && ch > 0;
                  const isDown = ch !== null && ch < 0;
                  const isVIX = m.ticker === "^VIX";
                  const sentimentColor = m.sentiment === "bullish" ? "#22c55e" : m.sentiment === "bearish" ? "#ef4444" : "#64748b";
                  const sentimentBg = m.sentiment === "bullish" ? "rgba(34,197,94,0.10)" : m.sentiment === "bearish" ? "rgba(239,68,68,0.10)" : "rgba(100,116,139,0.06)";
                  return (
                    <div
                      key={m.ticker}
                      className="rounded-xl p-3.5 transition-all flex flex-col gap-2"
                      style={{ border: "1px solid var(--term-border)", backgroundColor: sentimentBg }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono font-semibold tracking-tight" style={{ color: "var(--term-text)" }}>{m.label}</span>
                        <span className="text-[14px]" style={{ color: sentimentColor }}>
                          {m.sentiment === "bullish" ? "▲" : m.sentiment === "bearish" ? "▼" : "→"}
                        </span>
                      </div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-lg font-bold font-mono" style={{ color: "var(--term-text)" }}>
                          {m.price !== null ? `${m.price.toFixed(1)}` : "—"}
                        </span>
                        {ch !== null && (
                          <span
                            className="text-[11px] font-mono font-semibold px-1.5 py-0.5 rounded-md"
                            style={{
                              color: (isVIX ? !isUp : isUp) ? "#22c55e" : "#ef4444",
                              backgroundColor: (isVIX ? !isUp : isUp) ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                            }}
                          >
                            {isVIX && isDown ? "+" : isVIX && isUp ? "-" : isUp ? "+" : ""}{isVIX ? -ch.toFixed(1) : ch.toFixed(1)}%
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ── Row 5: Piyasa Modu + Kontrol Listesi ── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Piyasa Modu — canlı renk bar */}
              {(() => {
                const vix = stockResult.macro_indicators?.find(m => m.ticker === "^VIX");
                const vixVal = vix?.price;
                let mode = "Belirsiz";
                let modeColor = "#64748b";
                let modeBg = "rgba(100,116,139,0.10)";
                let modeGradient = "linear-gradient(135deg, rgba(100,116,139,0.15), rgba(100,116,139,0.05))";
                if (vixVal !== null && vixVal !== undefined) {
                  if (vixVal < 15) {
                    mode = "Risk-On (Sakin Piyasa)";
                    modeColor = "#22c55e";
                    modeBg = "rgba(34,197,94,0.10)";
                    modeGradient = "linear-gradient(135deg, rgba(34,197,94,0.18), rgba(16,185,129,0.05))";
                  } else if (vixVal < 20) {
                    mode = "Normal Piyasa";
                    modeColor = "#eab308";
                    modeBg = "rgba(234,179,8,0.10)";
                    modeGradient = "linear-gradient(135deg, rgba(234,179,8,0.18), rgba(250,204,21,0.05))";
                  } else if (vixVal < 30) {
                    mode = "Temkinli";
                    modeColor = "#f97316";
                    modeBg = "rgba(249,115,22,0.10)";
                    modeGradient = "linear-gradient(135deg, rgba(249,115,22,0.18), rgba(251,146,60,0.05))";
                  } else {
                    mode = "Panik Modu";
                    modeColor = "#ef4444";
                    modeBg = "rgba(239,68,68,0.10)";
                    modeGradient = "linear-gradient(135deg, rgba(239,68,68,0.18), rgba(248,113,113,0.05))";
                  }
                }
                return (
                  <div className="rounded-xl p-4 flex flex-col gap-3" style={{ border: "1px solid var(--term-border)", background: modeGradient }}>
                    <div className="flex items-center gap-2">
                      <span className="text-lg">
                        {vixVal !== null && vixVal !== undefined ? (vixVal < 15 ? "🟢" : vixVal < 20 ? "🟡" : vixVal < 30 ? "🟠" : "🔴") : "⚪"}
                      </span>
                      <span className="text-[10px] font-mono tracking-wider uppercase" style={{ color: "var(--term-muted)" }}>Piyasa Değerlendirmesi</span>
                    </div>
                    <div className="text-xl font-bold font-mono tracking-tight" style={{ color: modeColor }}>
                      {mode}
                    </div>
                    <div className="text-[11px] font-mono" style={{ color: "var(--term-muted)" }}>
                      VIX: {vixVal !== null && vixVal !== undefined ? vixVal.toFixed(1) : "—"} puan
                    </div>
                  </div>
                );
              })()}

              {/* Kontrol Listesi */}
              <div className="rounded-xl p-4 flex flex-col gap-3" style={{ border: "1px solid var(--term-border)", backgroundColor: "rgba(168,85,247,0.06)" }}>
                <div className="flex items-center gap-2">
                  <span className="text-lg">✅</span>
                  <span className="text-[10px] font-mono tracking-wider uppercase" style={{ color: "#a855f7" }}>Kontrol Listesi</span>
                </div>
                <div className="space-y-2">
                  {[
                    ["Bias Rule", stockResult.bias_pct !== null && stockResult.bias_pct > 5 ? "⚠ Buy Engellendi" : "✓ Geçti", stockResult.bias_pct !== null && stockResult.bias_pct > 5 ? "#ef4444" : "#22c55e"],
                    ["MA20 Sapma", stockResult.bias_pct !== null ? `%${stockResult.bias_pct.toFixed(1)}` : "—", stockResult.bias_pct !== null ? (stockResult.bias_pct < -5 ? "#22c55e" : "#eab308") : "#64748b"],
                    ["Pozisyon", stockResult.position_pl ? "Mevcut (P/L hesaplandı)" : "Boş — her iki öneri", "#06b6d4"],
                    ["Eksik Veri", stockResult.data_missing.length > 0 ? `${stockResult.data_missing.length} eksik` : "Tam", stockResult.data_missing.length > 0 ? "#eab308" : "#22c55e"],
                  ].map(([label, val, color]) => (
                    <div key={label as string} className="flex items-center justify-between">
                      <span className="text-[11px] font-mono" style={{ color: "var(--term-muted)" }}>{label}</span>
                      <span className="text-[11px] font-mono font-semibold" style={{ color: color as string }}>
                        {val}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Dividend result */}
      {tab === "dividend" && dividendResult && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-lg px-3 py-2" style={{ backgroundColor: "rgba(255,255,255,0.05)" }}>
            <span className="text-lg font-bold" style={{ color: "var(--term-text)" }}>{dividendResult.ticker}</span>
            {dividendResult.dividend_aristocrat && (
              <span className="rounded-full px-2 py-0.5 text-xs" style={{ backgroundColor: "rgba(168,85,247,0.20)", color: "#a855f7" }}>
                Temettü Aristokratı
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-lg px-3 py-2" style={{ backgroundColor: "rgba(255,255,255,0.05)" }}>
              <div className="text-xs" style={{ color: "var(--term-muted)" }}>Safety Score</div>
              <div className="text-lg font-bold" style={{ color: "var(--term-text)" }}>{dividendResult.safety_score}/100</div>
              <div className="text-xs" style={{ color: "var(--term-muted)" }}>{dividendResult.income_rating}</div>
            </div>
            <div className="rounded-lg px-3 py-2" style={{ backgroundColor: "rgba(255,255,255,0.05)" }}>
              <div className="text-xs" style={{ color: "var(--term-muted)" }}>Payout Status</div>
              <div className="text-lg font-bold capitalize" style={{ color: "var(--term-text)" }}>{dividendResult.payout_status}</div>
              <div className="text-xs" style={{ color: "var(--term-muted)" }}>
                {dividendResult.payout_ratio !== null
                  ? `%${(dividendResult.payout_ratio * 100).toFixed(1)}`
                  : "VERİ YOK"}
              </div>
            </div>
            <div className="rounded-lg px-3 py-2" style={{ backgroundColor: "rgba(255,255,255,0.05)" }}>
              <div className="text-xs" style={{ color: "var(--term-muted)" }}>5Y CAGR</div>
              <div className="text-lg font-bold" style={{ color: "var(--term-text)" }}>
                {dividendResult.cagr_5y !== null ? `%${dividendResult.cagr_5y}` : "VERİ YOK"}
              </div>
            </div>
            <div className="rounded-lg px-3 py-2" style={{ backgroundColor: "rgba(255,255,255,0.05)" }}>
              <div className="text-xs" style={{ color: "var(--term-muted)" }}>Artış Yılı</div>
              <div className="text-lg font-bold" style={{ color: "var(--term-text)" }}>
                {dividendResult.consecutive_growth_years !== null
                  ? `${dividendResult.consecutive_growth_years} yıl`
                  : "VERİ YOK"}
              </div>
            </div>
          </div>
          {dividendResult.current_yield !== null && (
            <div className="text-sm" style={{ color: "var(--term-muted)" }}>
              Güncünlük temettü verimi: <span className="font-bold" style={{ color: "var(--term-green)" }}>%{dividendResult.current_yield}</span>
            </div>
          )}
          {dividendResult.data_missing.length > 0 && (
            <div className="rounded-lg px-3 py-1.5 text-xs" style={{ border: "1px solid rgba(230,160,0,0.30)", backgroundColor: "rgba(230,160,0,0.10)", color: "var(--term-amber)" }}>
              Eksik veri: {dividendResult.data_missing.join(", ")}
            </div>
          )}
        </div>
      )}

      {/* Rumor signals */}
      {tab === "rumors" && rumorResult && (
        <div className="space-y-2">
          <div className="flex items-center justify-between rounded-lg px-3 py-2" style={{ backgroundColor: "rgba(255,255,255,0.05)" }}>
            <span className="text-sm" style={{ color: "var(--term-muted)" }}>
              Sorgu: <span style={{ color: "var(--term-text)" }}>{rumorResult.query || "piyasa geneli"}</span>
            </span>
            <span className="text-sm" style={{ color: "var(--term-amber)" }}>
              Toplam etki: <span className="font-bold">{rumorResult.total_impact}</span>
            </span>
          </div>
          {rumorResult.signals.length === 0 ? (
            <div className="text-sm" style={{ color: "var(--term-muted)" }}>Sinyal bulunamadı.</div>
          ) : (
            rumorResult.signals.map((s, i) => (
              <div key={i} className="rounded-lg p-2" style={{ border: "1px solid var(--term-border)", backgroundColor: "var(--term-bg)" }}>
                <div className="flex items-center gap-2">
                  <span className="rounded-full px-2 py-0.5 text-xs" style={
                    SIGNAL_TYPE_STYLES[s.signal_type] ?? { backgroundColor: "rgba(107,114,128,0.20)", color: "var(--term-muted)" }
                  }>
                    {s.signal_type} (+{s.impact_score})
                  </span>
                  <a
                    href={s.url ?? "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm"
                    style={{ color: "var(--term-text)" }}
                  >
                    {s.headline}
                  </a>
                </div>
                {s.summary && (
                  <div className="mt-1 text-xs" style={{ color: "var(--term-muted)" }}>{s.summary}</div>
                )}
                {s.source && (
                  <div className="mt-1 text-xs" style={{ color: "var(--term-muted)" }}>Kaynak: {s.source}</div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Kline result */}
      {tab === "kline" && klineResult && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-lg px-3 py-2" style={{ backgroundColor: "rgba(255,255,255,0.05)" }}>
            <span className="text-lg font-bold" style={{ color: "var(--term-text)" }}>{klineResult.ticker}</span>
            <span className="rounded-full px-2 py-0.5 text-xs" style={{ backgroundColor: "rgba(230,160,0,0.20)", color: "var(--term-amber)" }}>
              Pattern: {klineResult.pattern_detected || "none"}
            </span>
            {klineResult.used_fallback && (
              <span className="text-xs" style={{ color: "var(--term-amber)" }}>VLM yok → metin fallback</span>
            )}
          </div>
          {klineResult.error && (
            <div className="rounded-lg px-3 py-2 text-sm" style={{ border: "1px solid rgba(248,113,113,0.30)", backgroundColor: "rgba(248,113,113,0.10)", color: "var(--term-red)" }}>
              {klineResult.error}
            </div>
          )}
          {klineResult.chart_png_base64 && (
            <img
              src={`data:image/png;base64,${klineResult.chart_png_base64}`}
              alt={`${klineResult.ticker} candlestick`}
              className="rounded-lg" style={{ border: "1px solid var(--term-border)" }}
            />
          )}
          {klineResult.vlm_analysis && (
            <div className="rounded-lg p-3 text-sm whitespace-pre-wrap" style={{ backgroundColor: "rgba(255,255,255,0.05)", color: "var(--term-text)" }}>
              {klineResult.vlm_analysis}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
