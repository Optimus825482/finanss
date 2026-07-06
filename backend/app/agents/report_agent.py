"""
ReportAgent (Rapor)
Diğer dört ajanın çıktısını ağırlıklandırıp bileşik skor üretir, en iyi N
adayı seçer ve her biri için kısa, jargonsuz Türkçe gerekçe yazar.
"""
import asyncio

from app.agents.base import BaseAgent, AgentStatus
from app.config import SCORING_WEIGHTS, TOP_N_PICKS


def _narrative_for(c: dict) -> str:
    ticker = c["ticker"]
    parts = []

    if c["momentum_pct"] > 0:
        parts.append(f"{ticker} son bir haftada fiyatını %{c['momentum_pct']} artırdı")
    else:
        parts.append(f"{ticker} son bir haftada %{abs(c['momentum_pct'])} geriledi")

    if c["fundamental_score"] >= 70:
        parts.append("finansal tablolar sağlam görünüyor")
    elif c["fundamental_score"] <= 40:
        parts.append("finansal tablolarda dikkat edilmesi gereken zayıflıklar var")

    if c["sentiment_score"] >= 65:
        parts.append("haber akışı olumlu")
    elif c["sentiment_score"] <= 40:
        parts.append("haber akışı temkinli veya olumsuz")

    if c["risk_score"] >= 65:
        parts.append("fiyat hareketleri sert, temkinli pozisyon önerilir")
    elif c["risk_score"] <= 35:
        parts.append("fiyat hareketleri nispeten sakin")

    return ", ".join(parts) + "."


class ReportAgent(BaseAgent):
    name = "report"
    label = "Rapor"

    async def run(self, candidates: list[dict]) -> dict:
        self._set(AgentStatus.RUNNING, "Skorlar birleştiriliyor, rapor yazılıyor")
        try:
            result = await asyncio.to_thread(self._compose, candidates)
            self._set(AgentStatus.DONE, f"{len(result['picks'])} hisse önerisiyle rapor hazır")
            return result
        except Exception as e:
            self._set(AgentStatus.ERROR, str(e))
            raise

    def _compose(self, candidates: list[dict]) -> dict:
        w = SCORING_WEIGHTS
        for c in candidates:
            risk_inverse = 100 - c["risk_score"]
            c["composite_score"] = round(
                c["fundamental_score"] * w["fundamental"]
                + c["sentiment_score"] * w["sentiment"]
                + risk_inverse * w["risk"],
                1,
            )
            c["narrative"] = _narrative_for(c)

        candidates.sort(key=lambda x: x["composite_score"], reverse=True)
        top_picks = candidates[:TOP_N_PICKS]

        if top_picks:
            best = top_picks[0]
            summary = (
                f"Bugün {len(candidates)} sembol tarandı, en güçlü aday {best['ticker']} oldu "
                f"({best['composite_score']} bileşik puan). "
                f"Genel tabloda {'olumlu' if best['sentiment_score'] >= 55 else 'karışık'} bir haber "
                f"akışı ve {'düşük' if best['risk_score'] <= 45 else 'yüksek'} risk profili öne çıkıyor."
            )
        else:
            summary = "Bugün tarama kriterlerini geçen bir aday bulunamadı."

        return {
            "summary": summary,
            "candidates_scanned": len(candidates),
            "picks": top_picks,
        }
