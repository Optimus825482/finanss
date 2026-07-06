"use client";

import { useEffect, useState, FormEvent } from "react";
import { api, WatchlistItem } from "../lib/api";

export default function WatchlistPanel() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [ticker, setTicker] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      setItems(await api.getWatchlist());
    } catch {
      setError("İzleme listesi yüklenemedi");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault();
    if (!ticker.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await api.addWatchlistItem(ticker.trim().toUpperCase(), notes.trim() || undefined);
      setTicker("");
      setNotes("");
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      setError(msg.includes("409") ? "Bu sembol zaten listede" : "Eklenemedi, sembolü kontrol et");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    await api.deleteWatchlistItem(id);
    await load();
  };

  return (
    <div className="border border-term-border bg-term-panel rounded-sm p-4">
      <div className="text-[11px] tracking-[0.2em] text-term-muted font-mono mb-3">
        İZLEME LİSTESİ
      </div>

      <form onSubmit={handleAdd} className="flex gap-2 mb-3">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="TICKER"
          className="flex-1 min-w-0 bg-term-bg border border-term-border rounded-sm px-2 py-1.5 text-xs font-mono text-term-text placeholder:text-term-muted focus:outline-none focus:border-term-amber"
        />
        <input
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="not (opsiyonel)"
          className="flex-1 min-w-0 bg-term-bg border border-term-border rounded-sm px-2 py-1.5 text-xs font-mono text-term-text placeholder:text-term-muted focus:outline-none focus:border-term-amber"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-3 py-1.5 border border-term-amber text-term-amber text-xs font-mono rounded-sm hover:bg-term-amber hover:text-term-bg transition-colors disabled:opacity-40 whitespace-nowrap"
        >
          EKLE
        </button>
      </form>

      {error && <div className="text-[11px] text-term-red font-mono mb-2">{error}</div>}

      <div className="space-y-1 max-h-72 overflow-y-auto">
        {items.length === 0 && (
          <div className="text-xs text-term-muted font-mono">İzleme listesi boş</div>
        )}
        {items.map((it) => (
          <div
            key={it.id}
            className="flex items-center justify-between border-b border-term-border/60 py-2 last:border-0"
          >
            <div>
              <div className="font-mono text-sm text-term-text">{it.ticker}</div>
              {it.notes && <div className="text-[10px] text-term-muted">{it.notes}</div>}
            </div>
            <div className="flex items-center gap-3">
              {it.price !== null ? (
                <div className="text-right font-mono text-xs">
                  <div className="text-term-text">${it.price.toFixed(2)}</div>
                  <div className={(it.change_pct ?? 0) >= 0 ? "text-term-green" : "text-term-red"}>
                    {it.change_pct !== null
                      ? `${it.change_pct >= 0 ? "▲" : "▼"} ${Math.abs(it.change_pct)}%`
                      : "—"}
                  </div>
                </div>
              ) : (
                <span className="text-[10px] text-term-muted font-mono">veri yok</span>
              )}
              <button
                onClick={() => handleDelete(it.id)}
                className="text-term-muted hover:text-term-red text-xs font-mono"
                title="Kaldır"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
