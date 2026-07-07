"use client";

import { useState } from "react";
import TickerDetail from "../components/TickerDetail";
import Loader from "../components/Loader";
import { useTickerDetail } from "../hooks/useTickerDetail";
import { useWatchlist } from "../hooks/useWatchlist";

export default function TakipPage() {
  const { items, remove } = useWatchlist();
  const { detail, detailLoading, loadDetail, period, interval: interval_, setPeriod, setInterval_ } = useTickerDetail();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  const handleSelect = (t: string) => {
    setSelectedTicker(t);
    loadDetail(t);
  };

  const handleDelete = async (id: number, tickerVal: string) => {
    await remove(id);
    if (selectedTicker === tickerVal) {
      setSelectedTicker(null);
      // detail sıfırlanması loadDetail tarafından yapılmıyor, manuel yapmıyoruz da.
      // remove işlemi sonrası loadDetail çağrılmadığı için mevcut detail kalır, sorun değil.
    }
  };

  return (
    <main className="min-h-screen px-6 py-8 max-w-5xl mx-auto">
      <div className="rounded-sm px-6 py-4 mb-6" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
        <h1 className="font-mono text-xl font-semibold mb-1" style={{ color: "var(--term-text)" }}>TAKİP LİSTESİ</h1>
        <p className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>
          Takibe aldığın semboller — detaylı analiz için tıkla
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sol: Liste */}
        <div className="lg:col-span-1">
          <div className="rounded-sm" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
            <div className="px-4 py-3 text-xs font-mono tracking-wider" style={{ color: "var(--term-muted)" }}>
              TAKİP EDİLENLER ({items.length})
            </div>
            {items.length === 0 && (
              <div className="text-sm font-mono text-center py-8" style={{ color: "var(--term-muted)" }}>
                Takip listesi boş. İzleme sayfasından ekleyebilirsin.
              </div>
            )}
            {items.map((it) => (
              <button key={it.id}
                onClick={() => handleSelect(it.ticker)}
                className="w-full flex items-center justify-between px-4 py-3 border-b last:border-0 text-left transition-none"
                style={{
                  borderColor: "var(--term-border)",
                  backgroundColor: selectedTicker === it.ticker ? "var(--term-border)" : "transparent",
                }}
              >
                <div className="font-mono text-sm font-semibold" style={{ color: "var(--term-text)" }}>{it.ticker}</div>
                <div className="flex items-center gap-3">
                  {it.price !== null ? (
                    <div className="text-right font-mono text-xs">
                      <div style={{ color: "var(--term-text)" }}>${it.price.toFixed(2)}</div>
                      <div style={{ color: (it.change_pct ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)" }}>
                        {it.change_pct !== null ? `${it.change_pct >= 0 ? "▲" : "▼"} ${Math.abs(it.change_pct)}%` : "—"}
                      </div>
                    </div>
                  ) : (
                    <span className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>—</span>
                  )}
                  <span onClick={(e) => { e.stopPropagation(); handleDelete(it.id, it.ticker); }}
                    className="text-xs font-mono cursor-pointer transition-none" style={{ color: "var(--term-muted)" }}>✕</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Sağ: Detay */}
        <div className="lg:col-span-3">
          {detailLoading && (
            <div className="rounded-sm" style={{ border: "1px solid var(--term-border)", backgroundColor: "var(--term-panel)" }}><Loader /></div>
          )}
          {!selectedTicker && !detailLoading && (
            <div className="rounded-sm p-12 text-center" style={{ border: "1px dashed var(--term-border)", backgroundColor: "var(--term-panel)" }}>
              <div className="text-sm font-mono" style={{ color: "var(--term-muted)" }}>Detaylı bilgi için bir sembol seç</div>
            </div>
          )}
          {detail && !detailLoading && <TickerDetail detail={detail} period={period} interval={interval_} onPeriodChange={setPeriod} onIntervalChange={setInterval_} />}
        </div>
      </div>
    </main>
  );
}
