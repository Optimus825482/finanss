"use client";

import { useState } from "react";
import { ExchangeBadge, SectorBadge } from "./TickerBadge";
import PriceChart from "./PriceChart";
import { api } from "../lib/api";

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
  const changeColor = (detail.change_pct ?? 0) >= 0 ? "var(--term-green)" : "var(--term-red)";

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
              {detail.currency === "TRY" ? "₺" : "$"}{detail.price?.toFixed(2) ?? "—"}
            </div>
            <div className="font-mono text-sm" style={{ color: changeColor }}>
              {detail.change_pct !== null ? `${detail.change_pct >= 0 ? "▲" : "▼"} ${Math.abs(detail.change_pct).toFixed(2)}%` : "—"}
              {detail.change !== null ? ` (${detail.change >= 0 ? "+" : ""}${detail.change.toFixed(2)})` : ""}
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
          <PriceChart data={detail.price_history} color={changeColor}
            period={period} interval={interval}
            onPeriodChange={onPeriodChange} onIntervalChange={onIntervalChange} />
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
