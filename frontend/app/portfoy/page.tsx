"use client";

import { useEffect, useState, FormEvent } from "react";
import { api, PortfolioSummary } from "../lib/api";

export default function PortfoyPage() {
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
  const borderColor = "var(--term-border)";

  return (
    <main className="min-h-screen px-6 py-8 max-w-5xl mx-auto">
      <div
        className="rounded-sm px-6 py-4 mb-6"
        style={{
          borderColor,
          backgroundColor: "var(--term-panel)",
          border: `1px solid ${borderColor}`,
        }}
      >
        <h1 className="font-mono text-xl font-semibold mb-1" style={{ color: "var(--term-text)" }}>
          SANAL PORTFÖY
        </h1>
        <p className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>
          Alım-satım pozisyonlarını takip et, kâr/zarar durumunu gör
        </p>
      </div>

      {/* Özet kartları */}
      {summary && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div
            className="rounded-sm p-4 text-center"
            style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}
          >
            <div className="text-xs font-mono tracking-wider mb-1" style={{ color: "var(--term-muted)" }}>
              MALİYET
            </div>
            <div className="font-mono text-lg font-semibold" style={{ color: "var(--term-text)" }}>
              ${summary.total_cost_basis.toFixed(2)}
            </div>
          </div>
          <div
            className="rounded-sm p-4 text-center"
            style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}
          >
            <div className="text-xs font-mono tracking-wider mb-1" style={{ color: "var(--term-muted)" }}>
              PİYASA DEĞERİ
            </div>
            <div className="font-mono text-lg font-semibold" style={{ color: "var(--term-text)" }}>
              ${summary.total_market_value.toFixed(2)}
            </div>
          </div>
          <div
            className="rounded-sm p-4 text-center"
            style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}
          >
            <div className="text-xs font-mono tracking-wider mb-1" style={{ color: "var(--term-muted)" }}>
              TOPLAM P/L
            </div>
            <div
              className="font-mono text-lg font-semibold"
              style={{ color: summary.total_pl >= 0 ? "var(--term-green)" : "var(--term-red)" }}
            >
              {summary.total_pl >= 0 ? "+" : ""}${summary.total_pl.toFixed(2)} ({summary.total_pl_pct.toFixed(1)}%)
            </div>
          </div>
        </div>
      )}

      {/* Pozisyon ekle */}
      <div
        className="rounded-sm p-4 mb-6"
        style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}
      >
        <div className="text-xs font-mono tracking-wider mb-3" style={{ color: "var(--term-muted)" }}>
          YENİ POZİSYON AÇ
        </div>
        <form onSubmit={handleAdd} className="flex gap-2">
          <input
            value={form.ticker}
            onChange={(e) => setForm({ ...form, ticker: e.target.value })}
            placeholder="TICKER"
            className="flex-1 min-w-0 rounded-sm px-3 py-2 text-sm font-mono focus:outline-none"
            style={{
              backgroundColor: "var(--term-bg)",
              border: `1px solid ${borderColor}`,
              color: "var(--term-text)",
            }}
          />
          <input
            value={form.quantity}
            onChange={(e) => setForm({ ...form, quantity: e.target.value })}
            placeholder="Adet"
            type="number"
            step="any"
            className="w-24 rounded-sm px-3 py-2 text-sm font-mono focus:outline-none"
            style={{
              backgroundColor: "var(--term-bg)",
              border: `1px solid ${borderColor}`,
              color: "var(--term-text)",
            }}
          />
          <input
            value={form.entry_price}
            onChange={(e) => setForm({ ...form, entry_price: e.target.value })}
            placeholder="Giriş $"
            type="number"
            step="any"
            className="w-28 rounded-sm px-3 py-2 text-sm font-mono focus:outline-none"
            style={{
              backgroundColor: "var(--term-bg)",
              border: `1px solid ${borderColor}`,
              color: "var(--term-text)",
            }}
          />
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 font-mono text-xs rounded-sm transition-none disabled:opacity-40 whitespace-nowrap"
            style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}
          >
            AÇ
          </button>
        </form>
        {error && <div className="text-xs font-mono mt-2" style={{ color: "var(--term-red)" }}>{error}</div>}
      </div>

      {/* Açık pozisyonlar */}
      <div
        className="rounded-sm"
        style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}
      >
        <div className="px-4 py-3 text-xs font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>
          AÇIK POZİSYONLAR ({openPositions.length})
        </div>
        {openPositions.length === 0 && (
          <div className="text-sm font-mono text-center py-8" style={{ color: "var(--term-muted)" }}>
            Açık pozisyon yok
          </div>
        )}
        {openPositions.map((p) => (
          <div
            key={p.id}
            className="flex items-center justify-between px-4 py-3 gap-3"
            style={{ borderTop: `1px solid ${borderColor}` }}
          >
            <div className="min-w-0">
              <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>
                {p.ticker}{" "}
                <span style={{ color: "var(--term-muted)" }}>x{p.quantity}</span>
              </div>
              <div className="text-xs font-mono mt-0.5" style={{ color: "var(--term-muted)" }}>
                Giriş ${p.entry_price.toFixed(2)} · {new Date(p.entry_date).toLocaleDateString("tr-TR")}
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {p.unrealized_pl !== null ? (
                <div className="text-right font-mono text-sm">
                  <div style={{ color: "var(--term-text)" }}>${p.market_value?.toFixed(2)}</div>
                  <div style={{ color: p.unrealized_pl >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                    {p.unrealized_pl >= 0 ? "+" : ""}${p.unrealized_pl.toFixed(2)} ({p.unrealized_pl_pct?.toFixed(1)}%)
                  </div>
                </div>
              ) : (
                <span className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>veri yok</span>
              )}
              <input
                placeholder="Çıkış $"
                value={closeInputs[p.id] ?? ""}
                onChange={(e) => setCloseInputs({ ...closeInputs, [p.id]: e.target.value })}
                className="w-20 rounded-sm px-2 py-1.5 text-xs font-mono focus:outline-none"
                style={{
                  backgroundColor: "var(--term-bg)",
                  border: `1px solid ${borderColor}`,
                  color: "var(--term-text)",
                }}
              />
              <button
                onClick={() => handleClose(p.id)}
                className="text-xs font-mono transition-none whitespace-nowrap"
                style={{ color: "var(--term-amber)" }}
              >
                KAPAT
              </button>
              <button
                onClick={() => handleDelete(p.id)}
                className="text-xs font-mono transition-none"
                style={{ color: "var(--term-muted)" }}
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Kapanmış pozisyonlar */}
      {closedPositions.length > 0 && (
        <div
          className="rounded-sm mt-6"
          style={{ border: `1px solid ${borderColor}`, backgroundColor: "var(--term-panel)" }}
        >
          <div className="px-4 py-3 text-xs font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>
            KAPANMIŞ POZİSYONLAR ({closedPositions.length})
          </div>
          {closedPositions.map((p) => {
            const realized = p.exit_price !== null ? (p.exit_price - p.entry_price) * p.quantity : null;
            return (
              <div
                key={p.id}
                className="flex items-center justify-between px-4 py-2.5 font-mono text-sm"
                style={{ borderTop: `1px solid ${borderColor}` }}
              >
                <span style={{ color: "var(--term-muted)" }}>
                  {p.ticker} x{p.quantity} @ ${p.entry_price.toFixed(2)} → ${p.exit_price?.toFixed(2)}
                </span>
                <span style={{ color: realized !== null && realized >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                  {realized !== null ? `${realized >= 0 ? "+" : ""}$${realized.toFixed(2)}` : "—"}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
