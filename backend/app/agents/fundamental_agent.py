"""
FundamentalAgent (Temel Analiz)
Her aday için F/K, PD/DD, özkaynak karlılığı, gelir büyümesi ve borçluluk
oranlarını çeker; bunları 0-100 aralığında tek bir temel analiz skoruna indirger.
"""
import asyncio
import yfinance as yf

from app.agents.base import BaseAgent, AgentStatus


def _score_pe(pe: float | None) -> float:
    if pe is None or pe <= 0:
        return 40  # veri yoksa nötr-altı puan
    # 10-25 bandı makul kabul edilir; çok düşük (şüpheli) veya çok yüksek (pahalı) puan kaybettirir
    if 10 <= pe <= 25:
        return 90
    if pe < 10:
        return 65
    if pe <= 40:
        return 55
    return 30


def _score_growth(growth: float | None) -> float:
    if growth is None:
        return 40
    pct = growth * 100
    if pct >= 20:
        return 95
    if pct >= 10:
        return 80
    if pct >= 0:
        return 60
    return 25


def _score_roe(roe: float | None) -> float:
    if roe is None:
        return 40
    pct = roe * 100
    if pct >= 20:
        return 90
    if pct >= 10:
        return 70
    if pct >= 0:
        return 50
    return 20


def _score_debt(debt_to_equity: float | None) -> float:
    if debt_to_equity is None:
        return 50
    if debt_to_equity <= 50:
        return 85
    if debt_to_equity <= 100:
        return 65
    if debt_to_equity <= 200:
        return 45
    return 25


class FundamentalAgent(BaseAgent):
    name = "fundamental"
    label = "Temel Analiz"

    async def run(self, candidates: list[dict]) -> list[dict]:
        self._set(AgentStatus.RUNNING, f"{len(candidates)} sembol için finansal veri çekiliyor")
        try:
            enriched = await asyncio.to_thread(self._analyze, candidates)
            self._set(AgentStatus.DONE, "Temel analiz tamamlandı")
            return enriched
        except Exception as e:
            self._set(AgentStatus.ERROR, str(e))
            raise

    def _analyze(self, candidates: list[dict]) -> list[dict]:
        from app.services.yf_utils import safe_ticker_info
        for c in candidates:
            info = safe_ticker_info(c["ticker"])

            pe = info.get("trailingPE")
            roe = info.get("returnOnEquity")
            growth = info.get("revenueGrowth")
            debt_to_equity = info.get("debtToEquity")

            scores = [
                _score_pe(pe),
                _score_growth(growth),
                _score_roe(roe),
                _score_debt(debt_to_equity),
            ]
            c["fundamental_score"] = round(sum(scores) / len(scores), 1)
            c["pe_ratio"] = pe

        return candidates
