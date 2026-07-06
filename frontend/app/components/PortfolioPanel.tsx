"use client";

import { useEffect, useState, FormEvent } from "react";
import { api, PortfolioSummary } from "../lib/api";

export default function PortfolioPanel() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [form, setForm] = useState({ ticker: "", quantity: "", entry_price: "" });
  const [closeInputs, setCloseInputs] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      setSummary(await api.getPortfolio());
    } catch {
      setError("Portföy yüklenemedi");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault();
    const qty = parseFloat(form.quantity);
    const price = parseFloat(form.entry_price);
    if (!form.ticker.trim() || !qty || !price) return;
    setLoading(true);
    setError(null);
    try {
      await api.addPortfolioPosition({
        ticker: form.ticker.trim().toUpperCase(),
        quantity: qty,
        entry_price: price,
      });
      setForm({ ticker: "", quantity: "", entry_price: "" });
      await load();
    } catch {
      setError("Pozisyon eklenemedi");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = async (id: number) => {
    const price = parseFloat(closeInputs[id] ?? "");
    if (!price) return;
    await api.closePortfolioPosition(id, price);
    setCloseInputs((prev) => ({ ...prev, [id]: "" }));
    await load();
  };

  const handleDelete = async (id: number) => {
    await api.deletePortfolioPosition(id);
    await load();
  };

  const openPositions = summary?.positions.filter((p) => p.status === "open") ?? [];
  const closedPositions = summary?.positions.filter((p) => p.status === "closed") ?? [];

  return (
    <div className="border border-term-border bg-term-panel rounded-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[11px] tracking-[0.2em] text-term-muted font-mono">SANAL PORTFÖY</div>
        {summary && summary.total_cost_basis > 0 && (
          <div className="text-right font-mono text-xs">
            <span className="text-term-muted mr-2">Toplam P/L</span>
            <span className={summary.total_pl >= 0 ? "text-term-green" : "text-term-red"}>
              {summary.total_pl >= 0 ? "+" : ""}${summary.total_pl.toFixed(2)} (
              {summary.total_pl_pct.toFixed(1)}%)
            </span>
          </div>
        )}
      </div>

      <form onSubmit={handleAdd} className="grid grid-cols-4 gap-2 mb-4">
        <input
          value={form.ticker}
          onChange={(e) => setForm({ ...form, ticker: e.target.value })}
          placeholder="TICKER"
          className="bg-term-bg border border-term-border rounded-sm px-2 py-1.5 text-xs font-mono text-term-text placeholder:text-term-muted focus:outline-none focus:border-term-amber"
        />
        <input
          value={form.quantity}
          onChange={(e) => setForm({ ...form, quantity: e.target.value })}
          placeholder="adet"
          type="number"
          step="any"
          className="bg-term-bg border border-term-border rounded-sm px-2 py-1.5 text-xs font-mono text-term-text placeholder:text-term-muted focus:outline-none focus:border-term-amber"
        />
        <input
          value={form.entry_price}
          onChange={(e) => setForm({ ...form, entry_price: e.target.value })}
          placeholder="giriş $"
          type="number"
          step="any"
          className="bg-term-bg border border-term-border rounded-sm px-2 py-1.5 text-xs font-mono text-term-text placeholder:text-term-muted focus:outline-none focus:border-term-amber"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-3 py-1.5 border border-term-amber text-term-amber text-xs font-mono rounded-sm hover:bg-term-amber hover:text-term-bg transition-colors disabled:opacity-40 whitespace-nowrap"
        >
          AÇ
        </button>
      </form>

      {error && <div className="text-[11px] text-term-red font-mono mb-2">{error}</div>}

      <div className="space-y-1 mb-4 max-h-64 overflow-y-auto">
        <div className="text-[10px] text-term-muted font-mono tracking-wider mb-1">
          AÇIK POZİSYONLAR
        </div>
        {openPositions.length === 0 && (
          <div className="text-xs text-term-muted font-mono">Açık pozisyon yok</div>
        )}
        {openPositions.map((p) => (
          <div
            key={p.id}
            className="flex items-center justify-between border-b border-term-border/60 py-2 last:border-0 gap-2"
          >
            <div>
              <div className="font-mono text-sm text-term-text">
                {p.ticker} <span className="text-term-muted text-xs">x{p.quantity}</span>
              </div>
              <div className="text-[10px] text-term-muted font-mono">
                Giriş ${p.entry_price.toFixed(2)}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {p.unrealized_pl !== null ? (
                <div className="text-right font-mono text-xs">
                  <div className="text-term-text">${p.market_value?.toFixed(2)}</div>
                  <div className={p.unrealized_pl >= 0 ? "text-term-green" : "text-term-red"}>
                    {p.unrealized_pl >= 0 ? "+" : ""}${p.unrealized_pl.toFixed(2)} (
                    {p.unrealized_pl_pct?.toFixed(1)}%)
                  </div>
                </div>
              ) : (
                <span className="text-[10px] text-term-muted font-mono">veri yok</span>
              )}
              <input
                placeholder="çıkış $"
                value={closeInputs[p.id] ?? ""}
                onChange={(e) => setCloseInputs({ ...closeInputs, [p.id]: e.target.value })}
                className="w-16 bg-term-bg border border-term-border rounded-sm px-1.5 py-1 text-[10px] font-mono text-term-text placeholder:text-term-muted focus:outline-none focus:border-term-amber"
              />
              <button
                onClick={() => handleClose(p.id)}
                className="text-[10px] text-term-amber font-mono hover:underline whitespace-nowrap"
              >
                KAPAT
              </button>
              <button
                onClick={() => handleDelete(p.id)}
                className="text-term-muted hover:text-term-red text-xs font-mono"
                title="Sil"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>

      {closedPositions.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] text-term-muted font-mono tracking-wider mb-1">
            KAPANMIŞ POZİSYONLAR
          </div>
          {closedPositions.map((p) => {
            const realized =
              p.exit_price !== null ? (p.exit_price - p.entry_price) * p.quantity : null;
            return (
              <div key={p.id} className="flex items-center justify-between py-1.5 text-xs font-mono">
                <span className="text-term-muted">
                  {p.ticker} x{p.quantity}
                </span>
                <span className={realized !== null && realized >= 0 ? "text-term-green" : "text-term-red"}>
                  {realized !== null ? `${realized >= 0 ? "+" : ""}$${realized.toFixed(2)}` : "—"}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
