"use client";

import { ExchangeBadge, SectorBadge } from "../components/TickerBadge";
import TickerDetail from "../components/TickerDetail";
import Loader from "../components/Loader";
import { useTickerSearch } from "../hooks/useTickerSearch";
import { useTickerDetail } from "../hooks/useTickerDetail";

export default function IzlemePage() {
  const { detail, detailLoading, loadDetail, period, interval: interval_, setPeriod, setInterval_ } = useTickerDetail();
  const {
    ticker, suggestions, showSuggestions, selectedIdx,
    inputRef, dropdownRef, handleTickerChange, handleKeyDown, selectSuggestion,
  } = useTickerSearch((t) => { loadDetail(t); });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker.trim()) loadDetail(ticker.trim().toUpperCase());
  };

  return (
    <main className="min-h-screen px-6 py-8 max-w-5xl mx-auto">
      <div className="rounded-sm px-6 py-4 mb-6" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
        <h1 className="font-mono text-xl font-semibold mb-1" style={{ color: "var(--term-text)" }}>İZLEME</h1>
        <p className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>
          Herhangi bir hisse senedini ara, anlık fiyat ve detaylı analizini gör
        </p>
      </div>

      {/* Arama */}
      <div className="rounded-sm p-4 mb-6" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              value={ticker}
              onChange={(e) => handleTickerChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => suggestions.length > 0}
              placeholder="Sembol ara (örn: AAPL, NVDA, THYAO.IS)"
              autoComplete="off"
              className="w-full rounded-sm px-3 py-2.5 text-sm font-mono focus:outline-none"
              style={{ backgroundColor: "var(--term-bg)", border: "1px solid var(--term-border)", color: "var(--term-text)" }}
            />
            {showSuggestions && suggestions.length > 0 && (
              <div ref={dropdownRef} className="absolute top-full left-0 right-0 mt-1 rounded-sm z-50 overflow-hidden"
                style={{ backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)", boxShadow: "0 8px 24px rgba(0,0,0,0.3)" }}>
                {suggestions.map((s, idx) => (
                  <button key={s.ticker} type="button" onClick={() => selectSuggestion(s.ticker)}
                    className="w-full text-left px-3 py-2.5 transition-none"
                    style={{ backgroundColor: idx === selectedIdx ? "var(--term-border)" : "transparent" }}>
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-sm font-semibold shrink-0" style={{ color: "var(--term-amber)" }}>{s.ticker}</span>
                      <span className="text-xs truncate" style={{ color: "var(--term-text)" }}>{s.name}</span>
                      {s.sector && <SectorBadge sector={s.sector} />}
                      <ExchangeBadge exchange={s.exchange} name={s.exchange_name || s.exchange} />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
          <button type="submit"
            className="px-5 py-2.5 font-mono text-xs rounded-sm transition-none disabled:opacity-40 whitespace-nowrap"
            style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>
            ARA
          </button>
        </form>
      </div>

      {/* Sonuç */}
      {detailLoading && (<div className="rounded-sm" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}><Loader /></div>)}

      {!detail && !detailLoading && (
        <div className="rounded-sm p-12 text-center" style={{ border: "1px dashed var(--term-border)", backgroundColor: "var(--term-panel)" }}>
          <div className="text-sm font-mono" style={{ color: "var(--term-muted)" }}>Analiz etmek istediğin bir sembol ara</div>
        </div>
      )}

      {detail && !detailLoading && <TickerDetail detail={detail} period={period} interval={interval_} onPeriodChange={setPeriod} onIntervalChange={setInterval_} />}
    </main>
  );
}
