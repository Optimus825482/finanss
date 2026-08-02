"use client";

import { useEffect, useMemo, useState } from "react";
import { ExchangeBadge, SectorBadge } from "./TickerBadge";
import PriceChart from "./PriceChart";
import { api, apiFetch } from "../lib/api";

export interface TickerDetailData {
  ticker: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  change: number | null;
  previous_close: number | null;
  open: number | null;
  day_high: number | null;
  day_low: number | null;
  volume: number | null;
  avg_volume: number | null;
  market_cap: number | null;
  sector: string;
  industry: string;
  exchange: string;
  exchange_name: string;
  currency: string;
  pe_ratio: number | null;
  peg_ratio: number | null;
  pb_ratio: number | null;
  eps: number | null;
  roe: number | null;
  debt_to_equity: number | null;
  dividend_yield: number | null;
  revenue_growth: number | null;
  beta: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  fifty_day_avg: number | null;
  two_hundred_day_avg: number | null;
  description: string;
  website: string;
  country: string;
  employees: number | null;
  news: { title: string; link: string; publisher: string; published: string }[];
  price_history: { date: string; open: number; high: number; low: number; close: number; volume: number }[];
}

function formatLargeNum(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString()}`;
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  const pct = v * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

export interface OpenPosition {
  id: number;
  ticker: string;
  quantity: number;
  entry_price: number | null;
  entry_date: string;
  status: string;
  exit_price: number | null;
  exit_date: string | null;
  notes: string | null;
  current_price: number | null;
  market_value: number | null;
  unrealized_pl: number | null;
  unrealized_pl_pct: number | null;
}

interface TickerDetailProps {
  detail: TickerDetailData;
  period?: string;
  interval?: string;
  onPeriodChange?: (p: string) => void;
  onIntervalChange?: (i: string) => void;
}

export default function TickerDetail({ detail, period, interval, onPeriodChange, onIntervalChange }: TickerDetailProps) {
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisMsg, setAnalysisMsg] = useState<string | null>(null);
  const [addWatchlistLoading, setAddWatchlistLoading] = useState(false);
  const [addWatchlistMsg, setAddWatchlistMsg] = useState<string | null>(null);
  const [tick, setTick] = useState<{ price: number; change: number | null; change_pct: number | null } | null>(null);
  const [positions, setPositions] = useState<OpenPosition[]>([]);

  // 1sn canlı tick — fiyat + açık pozisyon P/L; tam detay 30sn'de useTickerDetail yeniler
  useEffect(() => {
    if (!detail.ticker) return;
    let alive = true;
    const id = setInterval(async () => {
      try {
        const [res, posRes] = await Promise.all([
          apiFetch(`/api/screener/${encodeURIComponent(detail.ticker)}/tick`, { cache: "no-store" }),
          apiFetch(`/api/portfolio/open/${encodeURIComponent(detail.ticker)}`, { cache: "no-store" }),
        ]);
        if (res.ok && alive) setTick(await res.json());
        if (posRes.ok && alive) setPositions(await posRes.json());
      } catch { /* poll zaten tekrar dener */ }
    }, 1000);
    return () => { alive = false; clearInterval(id); };
  }, [detail.ticker]);

  // Grafik son barını tick ile canlı güncelle (yeni reference → PriceChart data effect tetiklenir)
  const liveHistory = useMemo<typeof detail.price_history>(() => {
    if (!tick) return detail.price_history;
    const h = detail.price_history.slice();
    const last = h[h.length - 1];
    if (!last) return h;
    h[h.length - 1] = {
      ...last,
      close: tick.price,
      high: Math.max(last.high ?? last.close, tick.price),
      low: Math.min(last.low ?? last.close, tick.price),
    };
    return h;
  }, [detail.price_history, tick]);

  const price = tick?.price ?? detail.price;
  const changePct = tick?.change_pct ?? detail.change_pct;
  const change = tick?.change ?? detail.change;
  const changeColor = (changePct ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)";

  const handleDeepAnalyze = async () => {
    setAnalyzing(true);
    setAnalysisMsg(null);
    try {
      await api.analyzeTicker(detail.ticker);
      setAnalysisMsg("Agent team analize başladı. Tamamlandığında raporlar sayfasında görüntüleyebilirsin.");
    } catch {
      setAnalysisMsg("Analiz başlatılamadı, pipeline zaten çalışıyor olabilir.");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Başlık + Fiyat */}
      <div className="rounded-sm p-5" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="font-mono text-xl font-bold" style={{ color: "var(--term-text)" }}>{detail.ticker}</span>
              {detail.sector && <SectorBadge sector={detail.sector} />}
              <ExchangeBadge exchange={detail.exchange} name={detail.exchange_name} />
            </div>
            <div className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>
              {detail.name} · {detail.country} · {detail.industry}
            </div>
          </div>
          <div className="text-right">
            <div className="font-mono text-2xl font-bold" style={{ color: "var(--term-amber)" }}>
              {detail.currency === "TRY" ? "₺" : "$"}{price?.toFixed(2) ?? "—"}
            </div>
            <div className="font-mono text-sm" style={{ color: changeColor }}>
              {changePct !== null ? `${changePct >= 0 ? "▲" : "▼"} ${Math.abs(changePct).toFixed(2)}%` : "—"}
              {change !== null ? ` (${change >= 0 ? "+" : ""}${change.toFixed(2)})` : ""}
            </div>
            <button onClick={async()=>{
              setAddWatchlistLoading(true);
              try{
                await api.addWatchlistItem(detail.ticker);
                setAddWatchlistMsg("✓ Takibe eklendi");
              }catch(e){
                const msg=e instanceof Error?e.message:"";
                setAddWatchlistMsg(msg.includes("409")?"Zaten listede":"Eklenemedi");
              }
              setAddWatchlistLoading(false);
              setTimeout(()=>setAddWatchlistMsg(null),2000);
            }} disabled={addWatchlistLoading}
              className="font-mono text-[10px] mt-1 px-2 py-0.5 rounded-sm transition-none disabled:opacity-40"
              style={{border:"1px solid var(--term-border)",color:"var(--term-muted)"}}>
              {addWatchlistLoading?"…":addWatchlistMsg||"+ TAKİBE EKLE"}
            </button>
          </div>
        </div>
        <button onClick={handleDeepAnalyze} disabled={analyzing}
          className="w-full font-mono text-xs tracking-wider py-2.5 rounded-sm transition-none disabled:opacity-40"
          style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>
          {analyzing ? "AGENT TEAM ÇALIŞIYOR…" : "▶ DETAYLI ANALİZ ET"}
        </button>
        {analysisMsg && (
          <div className="text-xs font-mono mt-2" style={{ color: "var(--term-amber)" }}>{analysisMsg}</div>
        )}
      </div>

      {/* Grafik */}
      {detail.price_history.length > 0 && (
        <div className="rounded-sm p-4" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
          <div className="text-[11px] tracking-[0.2em] font-mono mb-2" style={{ color: "var(--term-muted)" }}>FİYAT GRAFİĞİ (30 GÜN)</div>
          <PriceChart data={liveHistory} color={changeColor}
            period={period} interval={interval}
            onPeriodChange={onPeriodChange} onIntervalChange={onIntervalChange} />
        </div>
      )}

      {/* Açık Pozisyonlar · Canlı K/Z */}
      {positions.length > 0 && (
        <div className="rounded-sm p-4" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
          <div className="flex items-center justify-between mb-3">
            <div className="text-[11px] tracking-[0.2em] font-mono" style={{ color: "var(--term-muted)" }}>AÇIK POZİSYONLAR · CANLI KÂR/ZARAR</div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--term-green)", animation: "pulse 1.5s infinite" }} />
              <span className="text-[10px] font-mono" style={{ color: "var(--term-muted)" }}>CANLI</span>
            </div>
          </div>
          <div className="space-y-2">
            {positions.map((p) => {
              const livePrice = tick?.price ?? p.current_price;
              const cost = (p.entry_price ?? 0) * p.quantity;
              const mv = livePrice != null ? livePrice * p.quantity : null;
              const pl = mv != null ? mv - cost : null;
              const plPct = cost > 0 && pl != null ? (pl / cost) * 100 : null;
              const plColor = (pl ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)";
              return (
                <div key={p.id} className="flex items-center justify-between font-mono text-xs border-b border-dashed pb-2 last:border-0" style={{ borderColor: "var(--term-border)" }}>
                  <div className="flex items-center gap-4">
                    <div>
                      <div style={{ color: "var(--term-text)" }}>{p.quantity} {detail.ticker}</div>
                      <div className="text-[10px]" style={{ color: "var(--term-muted)" }}>
                        Giriş ${(p.entry_price ?? 0).toFixed(2)} · {new Date(p.entry_date).toLocaleDateString("tr-TR")}
                      </div>
                    </div>
                    <div className="text-[10px]" style={{ color: "var(--term-muted)" }}>
                      <div>Maliyet ${cost.toFixed(2)}</div>
                      <div>Güncel {livePrice != null ? `$${livePrice.toFixed(2)}` : "—"}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div style={{ color: plColor }}>
                      {pl != null ? `${pl >= 0 ? "+" : ""}$${pl.toFixed(2)}` : "—"}
                    </div>
                    <div className="text-[10px]" style={{ color: plColor }}>
                      {plPct != null ? `${plPct >= 0 ? "+" : ""}${plPct.toFixed(2)}%` : "—"}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Finansal + Haberler */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-sm p-4" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
          <div className="text-[11px] tracking-[0.2em] font-mono mb-3" style={{ color: "var(--term-muted)" }}>FİNANSAL VERİLER</div>
          <div className="space-y-2">
            {[
              ["Piyasa Değeri", formatLargeNum(detail.market_cap)],
              ["F/K", detail.pe_ratio?.toFixed(2) ?? "—"],
              ["PEG", detail.peg_ratio?.toFixed(2) ?? "—"],
              ["P/D", detail.pb_ratio?.toFixed(2) ?? "—"],
              ["EPS", detail.eps != null ? `$${detail.eps.toFixed(2)}` : "—"],
              ["Özsermaye Karlılığı", detail.roe != null ? fmtPct(detail.roe) : "—"],
              ["Temettü Verimi", detail.dividend_yield != null ? fmtPct(detail.dividend_yield) : "—"],
              ["Gelir Büyümesi", detail.revenue_growth != null ? fmtPct(detail.revenue_growth) : "—"],
              ["Borç/Özsermaye", detail.debt_to_equity?.toFixed(2) ?? "—"],
              ["Beta", detail.beta?.toFixed(2) ?? "—"],
              ["52 Hafta Yüksek", detail.fifty_two_week_high != null ? `$${detail.fifty_two_week_high.toFixed(2)}` : "—"],
              ["52 Hafta Düşük", detail.fifty_two_week_low != null ? `$${detail.fifty_two_week_low.toFixed(2)}` : "—"],
              ["50 Gün Ort.", detail.fifty_day_avg != null ? `$${detail.fifty_day_avg.toFixed(2)}` : "—"],
              ["200 Gün Ort.", detail.two_hundred_day_avg != null ? `$${detail.two_hundred_day_avg.toFixed(2)}` : "—"],
              ["Çalışan", detail.employees?.toLocaleString() ?? "—"],
            ].map(([label, value]) => (
              <div key={label as string} className="flex justify-between text-xs font-mono border-b border-dashed pb-1" style={{ borderColor: "var(--term-border)" }}>
                <span style={{ color: "var(--term-muted)" }}>{label}</span>
                <span style={{ color: "var(--term-text)" }}>{value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-sm p-4" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
          <div className="text-[11px] tracking-[0.2em] font-mono mb-3" style={{ color: "var(--term-muted)" }}>SON HABERLER</div>
          {(!detail.news || detail.news.length === 0) && (
            <div className="text-xs font-mono" style={{ color: "var(--term-muted)" }}>Haber bulunamadı</div>
          )}
          <div className="space-y-3">
            {detail.news?.slice(0, 6).map((n, i) => (
              <a key={i} href={n.link} target="_blank" rel="noopener noreferrer" className="block transition-none">
                <div className="text-xs font-mono leading-snug mb-0.5" style={{ color: "var(--term-text)" }}>{n.title}</div>
                <div className="text-[10px] font-mono" style={{ color: "var(--term-muted)" }}>
                  {n.publisher} · {n.published ? new Date(n.published).toLocaleDateString("tr-TR") : ""}
                </div>
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* Şirket Profili */}
      {detail.description && (
        <div className="rounded-sm p-4" style={{ borderColor: "var(--term-border)", backgroundColor: "var(--term-panel)", border: "1px solid var(--term-border)" }}>
          <div className="text-[11px] tracking-[0.2em] font-mono mb-2" style={{ color: "var(--term-muted)" }}>ŞİRKET PROFİLİ</div>
          <p className="text-xs leading-relaxed" style={{ color: "var(--term-text)" }}>
            {detail.description.slice(0, 500)}{detail.description.length > 500 ? "…" : ""}
          </p>
          {detail.website && (
            <a href={detail.website} target="_blank" rel="noopener noreferrer"
              className="text-xs font-mono mt-2 inline-block transition-none" style={{ color: "var(--term-amber)" }}>
              {detail.website}
            </a>
          )}
        </div>
      )}
    </div>
  );
}
