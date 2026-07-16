"use client";

import { useState, FormEvent, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
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

const CONCLUSION_COLORS: Record<string, string> = {
  strong_buy: "text-green-400 font-bold",
  buy: "text-green-300",
  hold: "text-yellow-300",
  sell: "text-red-300",
  strong_sell: "text-red-400 font-bold",
  unknown: "text-gray-400",
};

const SIGNAL_COLORS: Record<string, string> = {
  ma: "bg-purple-500/20 text-purple-300",
  insider: "bg-blue-500/20 text-blue-300",
  analyst: "bg-cyan-500/20 text-cyan-300",
  regulatory: "bg-orange-500/20 text-orange-300",
  earnings: "bg-gray-500/20 text-gray-300",
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
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 backdrop-blur">
      <div className="mb-4 flex flex-wrap gap-2">
        {(Object.keys(TAB_LABELS) as SkillTab[]).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`rounded-lg px-3 py-1.5 text-sm transition ${
              tab === k
                ? "bg-cyan-500/30 text-cyan-200 ring-1 ring-cyan-400/50"
                : "bg-white/5 text-gray-400 hover:bg-white/10"
            }`}
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
            placeholder={tab === "rumors" ? "Ticker veya boş (piyasa geneli)" : "Ticker (örn AAPL)"}
            className="w-full rounded-lg border border-white/10 bg-slate-950/50 px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:border-cyan-400/50 focus:outline-none"
          />
          {suggLoading && (
            <div className="absolute right-3 top-2.5 text-xs text-gray-500">aranıyor…</div>
          )}
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute z-50 mt-1 w-full rounded-lg border border-white/10 bg-slate-900 shadow-xl max-h-72 overflow-auto">
              {suggestions.map((s) => (
                <button
                  key={`${s.ticker}-${s.exchange}`}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    selectSuggestion(s);
                  }}
                  className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-cyan-500/20 border-b border-white/5 last:border-0"
                >
                  <div className="min-w-0">
                    <span className="font-mono font-semibold text-cyan-300">{s.ticker}</span>
                    <span className="ml-2 truncate text-xs text-gray-400">{s.name}</span>
                  </div>
                  <span className="shrink-0 rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-gray-500">
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
              className="rounded-lg border border-white/10 bg-slate-950/50 px-2 py-2 text-sm text-white"
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
                  className="w-24 rounded-lg border border-white/10 bg-slate-950/50 px-2 py-2 text-sm text-white"
                />
                <input
                  type="number"
                  value={positionShares}
                  onChange={(e) => setPositionShares(e.target.value)}
                  placeholder="Adet"
                  className="w-20 rounded-lg border border-white/10 bg-slate-950/50 px-2 py-2 text-sm text-white"
                />
              </>
            )}
          </>
        )}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-200 ring-1 ring-cyan-400/50 transition hover:bg-cyan-500/30 disabled:opacity-50"
        >
          {loading ? "Çalışıyor..." : "Çalıştır"}
        </button>
      </form>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Stock analysis result — markdown */}
      {tab === "stock" && stockResult && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-lg bg-white/5 px-3 py-2">
            <span className="text-lg font-bold text-white">{stockResult.ticker}</span>
            <span className={`text-sm ${CONCLUSION_COLORS[stockResult.conclusion] ?? "text-gray-400"}`}>
              {stockResult.conclusion.toUpperCase().replace("_", " ")}
            </span>
            {stockResult.bias_pct !== null && (
              <span className="text-xs text-gray-400">
                乖离率: {stockResult.bias_pct > 0 ? "+" : ""}{stockResult.bias_pct}%
              </span>
            )}
          </div>
          {stockResult.data_missing.length > 0 && (
            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-3 py-1.5 text-xs text-yellow-300">
              Eksik veri: {stockResult.data_missing.join(", ")}
            </div>
          )}
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
              {stockResult.markdown}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* Dividend result */}
      {tab === "dividend" && dividendResult && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-lg bg-white/5 px-3 py-2">
            <span className="text-lg font-bold text-white">{dividendResult.ticker}</span>
            {dividendResult.dividend_aristocrat && (
              <span className="rounded-full bg-purple-500/20 px-2 py-0.5 text-xs text-purple-300">
                股息贵族 (Aristokrat)
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-lg bg-white/5 px-3 py-2">
              <div className="text-xs text-gray-400">Safety Score</div>
              <div className="text-lg font-bold text-white">{dividendResult.safety_score}/100</div>
              <div className="text-xs text-gray-400">{dividendResult.income_rating}</div>
            </div>
            <div className="rounded-lg bg-white/5 px-3 py-2">
              <div className="text-xs text-gray-400">Payout Status</div>
              <div className="text-lg font-bold text-white capitalize">{dividendResult.payout_status}</div>
              <div className="text-xs text-gray-400">
                {dividendResult.payout_ratio !== null
                  ? `%${(dividendResult.payout_ratio * 100).toFixed(1)}`
                  : "暂缺"}
              </div>
            </div>
            <div className="rounded-lg bg-white/5 px-3 py-2">
              <div className="text-xs text-gray-400">5Y CAGR</div>
              <div className="text-lg font-bold text-white">
                {dividendResult.cagr_5y !== null ? `%${dividendResult.cagr_5y}` : "暂缺"}
              </div>
            </div>
            <div className="rounded-lg bg-white/5 px-3 py-2">
              <div className="text-xs text-gray-400">Artış Yılı</div>
              <div className="text-lg font-bold text-white">
                {dividendResult.consecutive_growth_years !== null
                  ? `${dividendResult.consecutive_growth_years} yıl`
                  : "暂缺"}
              </div>
            </div>
          </div>
          {dividendResult.current_yield !== null && (
            <div className="text-sm text-gray-300">
              Güncünlük temettü verimi: <span className="font-bold text-green-300">%{dividendResult.current_yield}</span>
            </div>
          )}
          {dividendResult.data_missing.length > 0 && (
            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-3 py-1.5 text-xs text-yellow-300">
              Eksik veri: {dividendResult.data_missing.join(", ")}
            </div>
          )}
        </div>
      )}

      {/* Rumor signals */}
      {tab === "rumors" && rumorResult && (
        <div className="space-y-2">
          <div className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2">
            <span className="text-sm text-gray-400">
              Sorgu: <span className="text-white">{rumorResult.query || "piyasa geneli"}</span>
            </span>
            <span className="text-sm text-cyan-300">
              Toplam etki: <span className="font-bold">{rumorResult.total_impact}</span>
            </span>
          </div>
          {rumorResult.signals.length === 0 ? (
            <div className="text-sm text-gray-500">Sinyal bulunamadı.</div>
          ) : (
            rumorResult.signals.map((s, i) => (
              <div key={i} className="rounded-lg border border-white/10 bg-slate-950/40 p-2">
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${SIGNAL_COLORS[s.signal_type] ?? "bg-gray-500/20 text-gray-300"}`}>
                    {s.signal_type} (+{s.impact_score})
                  </span>
                  <a
                    href={s.url ?? "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-white hover:text-cyan-300"
                  >
                    {s.headline}
                  </a>
                </div>
                {s.summary && (
                  <div className="mt-1 text-xs text-gray-400">{s.summary}</div>
                )}
                {s.source && (
                  <div className="mt-1 text-xs text-gray-500">Kaynak: {s.source}</div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Kline result */}
      {tab === "kline" && klineResult && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-lg bg-white/5 px-3 py-2">
            <span className="text-lg font-bold text-white">{klineResult.ticker}</span>
            <span className="rounded-full bg-cyan-500/20 px-2 py-0.5 text-xs text-cyan-300">
              Pattern: {klineResult.pattern_detected || "none"}
            </span>
            {klineResult.used_fallback && (
              <span className="text-xs text-yellow-300">VLM yok → metin fallback</span>
            )}
          </div>
          {klineResult.error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {klineResult.error}
            </div>
          )}
          {klineResult.chart_png_base64 && (
            <img
              src={`data:image/png;base64,${klineResult.chart_png_base64}`}
              alt={`${klineResult.ticker} candlestick`}
              className="rounded-lg border border-white/10"
            />
          )}
          {klineResult.vlm_analysis && (
            <div className="rounded-lg bg-white/5 p-3 text-sm text-gray-200 whitespace-pre-wrap">
              {klineResult.vlm_analysis}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
