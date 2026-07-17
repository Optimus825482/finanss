"""
Bull/Bear Research Team — TradingAgents (UCLA/MIT) inspired.

Her aday için iki perspektiften yapılandırılmış analiz:
- Bull agent: Yükseliş katalizörleri, momentum, düşük değerleme, olumlu sinyaller
- Bear agent: Riskler, yüksek değerleme, olumsuz sinyaller, headwinds

Sentez: Consensus score + çatışan noktalar + risk-ödül profili.
"""
import asyncio
import logging
from typing import Optional

import numpy as np

from app.agents.base import BaseAgent, AgentStatus

logger = logging.getLogger(__name__)


class BullBearResearcher(BaseAgent):
    """Bir adayı hem bull hem bear perspektifinden değerlendirir."""

    name = "research"
    label = "Arastirma Ekibi"

    async def run(self, candidates: list[dict]) -> list[dict]:
        """Her aday için bull/bear skorları ve consensus hesapla."""
        self._set(AgentStatus.RUNNING, f"{len(candidates)} aday araştırılıyor")
        try:
            enriched = await asyncio.to_thread(self._analyze, candidates)
            self._set(AgentStatus.DONE, f"Araştırma tamamlandı: {len(candidates)} aday")
            return enriched
        except Exception as e:
            self._set(AgentStatus.ERROR, str(e))
            raise

    def _analyze(self, candidates: list[dict]) -> list[dict]:
        for c in candidates:
            ticker = c.get("ticker", "???")
            price = c.get("price", 0) or 0

            # ── Bull case ──
            bull_score = self._bull_case(c)

            # ── Bear case ──
            bear_score = self._bear_case(c)

            # ── Consensus ──
            consensus = round((bull_score - bear_score + 100) / 2, 1)  # 0-100 scale
            # Risk-ödül profili: bull yüksek + bear düşük = iyi fırsat
            risk_reward_profile = self._risk_reward_label(bull_score, bear_score)

            # Çatışan noktalar
            conflicts = self._detect_conflicts(c, bull_score, bear_score)

            c["bull_score"] = bull_score
            c["bear_score"] = bear_score
            c["consensus_score"] = consensus
            c["risk_reward_profile"] = risk_reward_profile
            c["research_conflicts"] = conflicts
            c["research_summary"] = self._generate_summary(
                ticker, bull_score, bear_score, consensus, risk_reward_profile, conflicts
            )

        return candidates

    def _bull_case(self, c: dict) -> float:
        """Bull skoru: yükseliş argümanlarının ağırlıklı toplamı (0-100)."""
        score = 50.0
        reasons = 0

        # Momentum (5d)
        mom = c.get("momentum_5d", c.get("momentum_pct", 0)) or 0
        if mom > 5:
            score += 35
        elif mom > 0:
            score += 20
        elif mom > -3:
            score += 5
        else:
            score -= 15
        reasons += 1

        # Composite / Technical score
        comp = c.get("composite_score", c.get("technical_score", 50)) or 50
        if comp >= 80:
            score += 30
        elif comp >= 65:
            score += 20
        elif comp >= 50:
            score += 5
        else:
            score -= 20
        reasons += 1

        # Fundamental score
        fund = c.get("fundamental_score", 50) or 50
        if fund >= 80:
            score += 25
        elif fund >= 60:
            score += 15
        elif fund >= 40:
            score += 5
        else:
            score -= 15
        reasons += 1

        # PE ratio: düşük PE → undervalued (bull argüman)
        pe = c.get("pe_ratio")
        if pe is not None and pe > 0:
            if pe < 10:
                score += 20
            elif pe < 20:
                score += 10
            elif pe > 40:
                score -= 10
            reasons += 1

        # Sentiment
        sent = c.get("sentiment_score", 50) or 50
        if sent >= 70:
            score += 15
        elif sent >= 55:
            score += 5
        elif sent < 40:
            score -= 10
        reasons += 1

        # RSI: aşırı satım → bull argüman (toparlanma potansiyeli)
        rsi = c.get("rsi_14")
        if rsi is not None:
            if 30 <= rsi <= 50:  # dibe yakın, toparlanma potansiyeli
                score += 10
            elif rsi > 70:
                score -= 15
            reasons += 1

        # Fair value margin
        margin = c.get("margin_pct")
        if margin is not None:
            if margin > 20:
                score += 20
            elif margin > 10:
                score += 10
            elif margin < -10:
                score -= 10
            reasons += 1

        raw = score / max(reasons, 1)
        # Normalize to 0-100
        return round(max(10.0, min(95.0, (raw / 100) * 100)), 1) if raw > 0 else 50.0

    def _bear_case(self, c: dict) -> float:
        """Bear skoru: risk ve düşüş argümanlarının ağırlıklı toplamı (0-100)."""
        score = 50.0
        reasons = 0

        # Risk score (ters: yüksek risk → yüksek bear)
        risk = c.get("risk_score", 50) or 50
        if risk >= 70:
            score += 35
        elif risk >= 55:
            score += 20
        elif risk < 35:
            score -= 20
        reasons += 1

        # Volatility
        vol = c.get("volatility", c.get("volatility_annualized"))
        if vol is not None:
            if vol > 50:
                score += 25
            elif vol > 30:
                score += 15
            elif vol < 20:
                score -= 10
            reasons += 1

        # PE: çok yüksek → expensive (bear argüman)
        pe = c.get("pe_ratio")
        if pe is not None and pe > 0:
            if pe > 40:
                score += 25
            elif pe > 25:
                score += 15
            elif pe < 8:
                score -= 10  # too cheap might be justified
            reasons += 1

        # Negative momentum
        mom = c.get("momentum_5d", c.get("momentum_pct", 0)) or 0
        if mom < -5:
            score += 30
        elif mom < -2:
            score += 15
        elif mom > 3:
            score -= 10
        reasons += 1

        # RSI: aşırı alım → bear argüman
        rsi = c.get("rsi_14")
        if rsi is not None:
            if rsi > 75:
                score += 25
            elif rsi > 65:
                score += 10
            reasons += 1

        # Low sentiment
        sent = c.get("sentiment_score", 50) or 50
        if sent < 35:
            score += 20
        elif sent < 45:
            score += 10
        reasons += 1

        # Negative fair value margin
        margin = c.get("margin_pct")
        if margin is not None:
            if margin < -15:
                score += 20
            elif margin < -5:
                score += 10
            reasons += 1

        raw = score / max(reasons, 1)
        return round(max(10.0, min(95.0, (raw / 100) * 100)), 1) if raw > 0 else 50.0

    def _risk_reward_label(self, bull: float, bear: float) -> str:
        """Risk-ödül profili etiketi."""
        ratio = bull / max(bear, 1)
        if ratio >= 1.8:
            return "strong_opportunity"
        elif ratio >= 1.3:
            return "good_opportunity"
        elif ratio >= 0.9:
            return "neutral"
        elif ratio >= 0.5:
            return "risky"
        return "high_risk"

    def _detect_conflicts(self, c: dict, bull: float, bear: float) -> list[str]:
        """Bull/bear arasındaki çatışan sinyalleri tespit et."""
        conflicts = []
        mom = c.get("momentum_5d", c.get("momentum_pct", 0)) or 0
        rsi = c.get("rsi_14")

        if mom > 5 and rsi is not None and rsi > 75:
            conflicts.append("Güçlü momentum ama RSI aşırı alım bölgesinde")
        if mom < -3 and rsi is not None and rsi < 30:
            conflicts.append("Düşüş trendi ama RSI aşırı satım (dip olabilir)")
        if (c.get("composite_score", 50) or 50) >= 70 and (c.get("risk_score", 50) or 50) >= 60:
            conflicts.append("Yüksek skor ama yüksek risk profili")
        pe = c.get("pe_ratio")
        if pe is not None and pe > 30 and (c.get("fundamental_score", 50) or 50) >= 60:
            conflicts.append("Yüksek F/K'ya rağmen temel analiz güçlü")

        return conflicts

    def _generate_summary(
        self, ticker: str, bull: float, bear: float, consensus: float,
        profile: str, conflicts: list[str],
    ) -> str:
        """İnsan-okunur araştırma özeti."""
        labels = {
            "strong_opportunity": "çok güçlü alım fırsatı",
            "good_opportunity": "iyi risk-ödül profili",
            "neutral": "dengeli görünüm",
            "risky": "riskli — temkinli olunmalı",
            "high_risk": "yüksek risk — kaçınılmalı",
        }
        parts = [f"{ticker}: Bull={bull:.0f} Bear={bear:.0f} Consensus={consensus:.0f}"]
        parts.append(f"Profil: {labels.get(profile, profile)}")
        if conflicts:
            parts.append(f"Çatışma: {'; '.join(conflicts[:2])}")
        return " | ".join(parts)
