"use client";

import { useState } from "react";
import { StockPick, API_BASE, apiHeaders, api } from "../lib/api";

function ScoreBar({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div>
      <div className="flex justify-between text-[10px] font-mono text-term-muted mb-1">
        <span>{label}</span>
        <span>{value.toFixed(0)}</span>
      </div>
      <div className="h-1.5 bg-term-border rounded-full overflow-hidden">
        <div className={`h-full ${tone}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
    </div>
  );
}

export default function StockCard({ pick, rank, showPredict }: { pick: StockPick; rank: number; showPredict?: boolean }) {
  const momentumPositive = pick.momentum_pct >= 0;
  const [predLoading, setPredLoading] = useState(false);
  const [prediction, setPrediction] = useState<any>(null);
  const [fairValue, setFairValue] = useState<any>(null);
  const [fvLoading, setFvLoading] = useState(false);

  const handlePredict = async () => {
    setPredLoading(true);
    try {
      setPrediction(await api.createPrediction(pick.ticker));
    } catch (e) { console.warn("Failed to get prediction", e); }
    setPredLoading(false);
  };

  return (
    <div className="border border-term-border bg-term-panel rounded-sm p-4 hover:border-term-amber/50 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[10px] text-term-muted">#{rank}</span>
            <span className="font-mono text-lg font-semibold text-term-text">{pick.ticker}</span>
          </div>
          <div className="font-mono text-sm text-term-muted mt-0.5">
            ${pick.price.toFixed(2)}{" "}
            <span className={momentumPositive ? "text-term-green" : "text-term-red"}>
              {momentumPositive ? "▲" : "▼"} {Math.abs(pick.momentum_pct)}%
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono text-2xl font-bold text-term-amber leading-none">
            {pick.composite_score.toFixed(0)}
          </div>
          <div className="font-mono text-[9px] text-term-muted tracking-wider">BİLEŞİK PUAN</div>
        </div>
      </div>

      <div className="space-y-2 mb-3">
        <ScoreBar label="TEMEL ANALİZ" value={pick.fundamental_score} tone="bg-term-green" />
        <ScoreBar label="SENTIMENT" value={pick.sentiment_score} tone="bg-term-amber" />
        <ScoreBar label="RİSK" value={pick.risk_score} tone="bg-term-red" />
      </div>

      <p className="text-xs text-term-text/80 leading-relaxed border-t border-term-border pt-3">
        {pick.narrative}
      </p>

      {(pick.pe_ratio || pick.volatility_annualized) && (
        <div className="flex gap-4 mt-3 pt-3 border-t border-term-border font-mono text-[10px] text-term-muted">
          {pick.pe_ratio && <span>F/K {pick.pe_ratio.toFixed(1)}</span>}
          {pick.volatility_annualized && <span>Vol %{pick.volatility_annualized}</span>}
          {pick.max_drawdown_pct && <span>Düşüş %{pick.max_drawdown_pct}</span>}
        </div>
      )}

      {showPredict !== false && (
        <div className="mt-3 pt-3 border-t border-term-border space-y-2">
          {/* Adil deger butonu */}
          {(fairValue
            ? <div className="flex flex-wrap gap-2 items-center">
                <span className="font-mono text-[10px]" style={{ color: "var(--term-amber)" }}>⚖</span>
                <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-sm" style={{ backgroundColor: fairValue.margin_pct > 0 ? "rgba(74,222,128,0.12)" : "rgba(248,113,113,0.12)", color: fairValue.margin_pct > 0 ? "var(--term-green)" : "var(--term-red)" }}>
                  Adil: ${fairValue.fair_value} ({fairValue.margin_pct > 0 ? "+" : ""}{fairValue.margin_pct}%)
                </span>
              </div>
            : <button onClick={()=>{setFvLoading(true);fetch(`${API_BASE}/api/screener/${pick.ticker}/fair-value`,{headers:apiHeaders()}).then(r=>r.json()).then(v=>{setFairValue(v);setFvLoading(false)}).catch(()=>setFvLoading(false))}} disabled={fvLoading}
                className="font-mono text-[10px] px-2.5 py-1 rounded-sm transition-none disabled:opacity-40"
                style={{ border: "1px solid var(--term-amber-dim)", color: "var(--term-amber-dim)" }}>
                {fvLoading ? "…" : "⚖ ADİL DEĞER"}
              </button>
          )}
          {/* Ongoru butonu */}
          {(prediction?.predictions
            ? <div className="flex flex-wrap gap-2 items-center">
                <span className="font-mono text-[10px]" style={{ color: "var(--term-amber)" }}>📈</span>
                {Object.entries(prediction.predictions).map(([k, v]: [string, any]) => (
                  <span key={k} className="font-mono text-[9px] px-1.5 py-0.5 rounded-sm" style={{ backgroundColor: "var(--term-bg)", color: "var(--term-muted)" }}>
                    {k.replace("day_", "")}g: ${v.predicted}
                  </span>
                ))}
              </div>
            : <button onClick={handlePredict} disabled={predLoading}
                className="font-mono text-[10px] px-2.5 py-1 rounded-sm transition-none disabled:opacity-40"
                style={{ border: "1px solid var(--term-amber)", color: "var(--term-amber)" }}>
                {predLoading ? "…" : "📈 ÖNGÖRÜ"}
              </button>
          )}
        </div>
      )}
    </div>
  );
}
