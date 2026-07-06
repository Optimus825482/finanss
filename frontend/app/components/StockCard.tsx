import { StockPick } from "../lib/api";

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

export default function StockCard({ pick, rank }: { pick: StockPick; rank: number }) {
  const momentumPositive = pick.momentum_pct >= 0;

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
    </div>
  );
}
