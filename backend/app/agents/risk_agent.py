"""
RiskAgent (Risk)
Tarama ajanının taşıdığı fiyat geçmişini kullanarak yıllıklandırılmış
volatilite, maksimum düşüş (drawdown) ve S&P 500'e göre beta hesaplar.
risk_score: 0 = düşük risk, 100 = yüksek risk.
"""
import asyncio
import numpy as np
import yfinance as yf

from app.agents.base import BaseAgent, AgentStatus
from app.config import BENCHMARK_TICKER


class RiskAgent(BaseAgent):
    name = "risk"
    label = "Risk"

    async def run(self, candidates: list[dict]) -> list[dict]:
        self._set(AgentStatus.RUNNING, "Volatilite ve düşüş analizi hesaplanıyor")
        try:
            enriched = await asyncio.to_thread(self._analyze, candidates)
            self._set(AgentStatus.DONE, "Risk analizi tamamlandı")
            return enriched
        except Exception as e:
            self._set(AgentStatus.ERROR, str(e))
            raise

    def _analyze(self, candidates: list[dict]) -> list[dict]:
        try:
            benchmark_hist = yf.Ticker(BENCHMARK_TICKER).history(period="3mo")["Close"]
            benchmark_returns = benchmark_hist.pct_change().dropna()
        except Exception:
            benchmark_returns = None

        for c in candidates:
            hist = c.get("history")
            if hist is None or hist.empty:
                c["risk_score"] = 50.0
                c["volatility_annualized"] = None
                c["max_drawdown_pct"] = None
                continue

            closes = hist["Close"]
            returns = closes.pct_change().dropna()

            volatility_annualized = float(returns.std() * np.sqrt(252) * 100) if len(returns) > 1 else 0.0

            running_max = closes.cummax()
            drawdown = (closes - running_max) / running_max
            max_drawdown_pct = float(drawdown.min() * 100)

            beta = None
            if benchmark_returns is not None and len(returns) > 5:
                aligned = returns.align(benchmark_returns, join="inner")
                r, b = aligned
                if len(r) > 5 and b.var() > 0:
                    beta = float(np.cov(r, b)[0][1] / b.var())

            # Risk skoru: yüksek volatilite + derin drawdown + yüksek beta -> yüksek risk
            vol_component = min(volatility_annualized / 60 * 100, 100)  # %60 yıllık vol = tavan
            dd_component = min(abs(max_drawdown_pct) / 40 * 100, 100)  # %40 düşüş = tavan
            beta_component = min(abs(beta) / 2 * 100, 100) if beta is not None else 50

            risk_score = round(vol_component * 0.45 + dd_component * 0.35 + beta_component * 0.20, 1)

            c["risk_score"] = risk_score
            c["volatility_annualized"] = round(volatility_annualized, 1)
            c["max_drawdown_pct"] = round(max_drawdown_pct, 1)
            c["beta"] = round(beta, 2) if beta is not None else None

            # Ham geçmiş veriyi rapora taşımıyoruz, DB'ye yazılmayacak
            c.pop("history", None)

        return candidates
