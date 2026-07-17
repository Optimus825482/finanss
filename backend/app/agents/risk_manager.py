"""
Risk Manager Agent — TradingAgents (UCLA/MIT) inspired.

Trade kararlarını piyasa koşullarına göre veto edebilir / ayarlayabilir:
- Piyasa volatilitesi eşik kontrolü
- Sektör exposure limit kontrolü
- Korelasyon bazlı çeşitlendirme zorlaması
- ATR trailing stop seviyeleri
- Stop-loss önerileri
"""
import logging
from typing import Optional

from app.agents.base import BaseAgent, AgentStatus

logger = logging.getLogger(__name__)

# Risk limits
MAX_SECTOR_EXPOSURE_PCT = 0.40        # Aynı sektöre max %40
MAX_CORRELATION = 0.75                # Bu korelasyonun üstünde pozisyon küçült
HIGH_VOL_THRESHOLD = 40.0             # %40 üzeri yıllık vol → yüksek risk
ATR_STOP_MULTIPLIER = 1.5             # ATR × 1.5 = trailing stop mesafesi
ATR_TAKE_PROFIT_MULTIPLIER = 3.0      # ATR × 3 = take-profit seviyesi

# Sektör mapping (BIST ve US için güncellenebilir)
SECTOR_MAP: dict[str, str] = {
    "THYAO.IS": "transportation", "PGSUS.IS": "transportation",
    "GARAN.IS": "banking", "AKBNK.IS": "banking", "YKBNK.IS": "banking",
    "HALKB.IS": "banking", "VAKBN.IS": "banking", "ISCTR.IS": "banking",
    "ASELS.IS": "defense", "OTKAR.IS": "defense",
    "EREGL.IS": "steel", "KRDMD.IS": "steel",
    "TUPRS.IS": "energy", "PETKM.IS": "energy", "SASA.IS": "energy",
    "SISE.IS": "glass", "SOKM.IS": "retail", "BIMAS.IS": "retail",
    "TCELL.IS": "telecom", "TTKOM.IS": "telecom",
    "KCHOL.IS": "holding", "SAHOL.IS": "holding", "SISE.IS": "conglomerate",
    "ARCLK.IS": "consumer", "VESTL.IS": "consumer",
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "AMZN": "technology", "META": "technology", "NVDA": "technology",
    "TSLA": "automotive", "F": "automotive", "GM": "automotive",
    "JPM": "banking", "BAC": "banking", "WFC": "banking", "GS": "banking",
    "XOM": "energy", "CVX": "energy", "COP": "energy",
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "WMT": "retail", "COST": "retail", "TGT": "retail",
    "BA": "defense", "LMT": "defense", "RTX": "defense",
}


class RiskManager(BaseAgent):
    """Trade öncesi risk değerlendirmesi yapar."""

    name = "risk_manager"
    label = "Risk Yöneticisi"

    def get_sector(self, ticker: str) -> str:
        """Hisse → sektör mapping (cache yok, basit dict lookup)."""
        return SECTOR_MAP.get(ticker.upper(), "other")

    def check_sector_exposure(
        self,
        ticker: str,
        positions: list[dict],
        max_exposure: float = MAX_SECTOR_EXPOSURE_PCT,
    ) -> tuple[bool, str]:
        """Bu ticker'ı eklemek sektör limitini aşar mı?"""
        sector = self.get_sector(ticker)
        sector_positions = [
            p for p in positions
            if self.get_sector(p.get("ticker", "")) == sector
        ]
        # Basit pozisyon sayısı kontrolü (ileride market value bazlı yapılabilir)
        total_positions = len(positions)
        if total_positions == 0:
            return True, "ok"

        current_sector_pct = len(sector_positions) / max(total_positions, 1)
        new_sector_pct = (len(sector_positions) + 1) / (total_positions + 1)

        if new_sector_pct > max_exposure:
            return False, (
                f"Sektör limiti aşıldı: {sector} sektöründe "
                f"{len(sector_positions)}/{total_positions} pozisyon "
                f"(%{new_sector_pct*100:.0f} > %{max_exposure*100:.0f})"
            )
        return True, "ok"

    def check_volatility_risk(
        self,
        volatility: Optional[float],
        threshold: float = HIGH_VOL_THRESHOLD,
    ) -> tuple[bool, str]:
        """Volatilite çok mu yüksek?"""
        if volatility is None:
            return True, "volatilite verisi yok — geçildi"
        if volatility >= threshold:
            return False, f"Yüksek volatilite: %{volatility:.1f} >= %{threshold:.1f}"
        return True, "ok"

    def check_correlation_risk(
        self,
        ticker: str,
        positions: list[dict],
        correlation_data: Optional[dict] = None,
        max_corr: float = MAX_CORRELATION,
    ) -> tuple[bool, str]:
        """Bu hisse mevcut pozisyonlarla çok mu korele?"""
        if not positions or correlation_data is None:
            return True, "ok"
        # Basitleştirilmiş: aynı sektör = yüksek korelasyon varsay
        sector = self.get_sector(ticker)
        same_sector = [
            p for p in positions
            if self.get_sector(p.get("ticker", "")) == sector
        ]
        if len(same_sector) >= 2:
            return False, (
                f"{sector} sektöründe zaten {len(same_sector)} pozisyon var — "
                f"korelasyon riski yüksek"
            )
        return True, "ok"

    def atr_stop_levels(
        self,
        current_price: float,
        volatility: Optional[float],
        entry_price: float,
    ) -> dict:
        """ATR-bazlı trailing stop ve take-profit seviyeleri."""
        if volatility is None or current_price <= 0:
            atr = current_price * 0.03  # varsayılan %3
        else:
            # Volatiliteden günlük ATR tahmini
            daily_vol = volatility / (252 ** 0.5) / 100
            atr = current_price * daily_vol

        stop_distance = atr * ATR_STOP_MULTIPLIER
        profit_distance = atr * ATR_TAKE_PROFIT_MULTIPLIER

        return {
            "atr": round(atr, 2),
            "trailing_stop": round(max(entry_price - stop_distance, entry_price * 0.85), 2),
            "take_profit": round(entry_price + profit_distance, 2),
            "stop_loss_pct": round((1 - max(entry_price - stop_distance, entry_price * 0.85) / entry_price) * 100, 1),
        }

    def evaluate(
        self,
        ticker: str,
        candidates: list[dict],
        positions: list[dict],
        volatility: Optional[float] = None,
        cash: float = 0,
    ) -> dict:
        """Kapsamlı risk değerlendirmesi.

        Returns:
            {
                "approved": bool,
                "veto_reasons": [...],
                "adjusted_budget_pct": float,  # 0.0-1.0 multiplier on Kelly budget
                "stop_levels": {...},
                "warnings": [...],
            }
        """
        veto_reasons = []
        warnings = []
        budget_multiplier = 1.0

        # 1. Volatilite kontrolü
        vol_ok, vol_msg = self.check_volatility_risk(volatility)
        if not vol_ok:
            veto_reasons.append(vol_msg)
            budget_multiplier *= 0.3  # volatil yüksekse çok az al

        # 2. Sektör exposure kontrolü
        sector_ok, sector_msg = self.check_sector_exposure(ticker, positions)
        if not sector_ok:
            veto_reasons.append(sector_msg)
            # veto etmiyoruz, sadece uyarı

        # 3. Korelasyon kontrolü
        corr_ok, corr_msg = self.check_correlation_risk(ticker, positions)
        if not corr_ok:
            warnings.append(corr_msg)
            budget_multiplier *= 0.5  # korele pozisyonu yarı boyutta al

        # 4. Price kontrolü
        candidate = next((c for c in candidates if c["ticker"] == ticker), None)
        if candidate:
            price = candidate.get("price", 0) or 0
            vol = candidate.get("volatility", volatility)
            entry = price  # current price ≈ entry

            # ATR stop levels
            stop_levels = self.atr_stop_levels(price, vol, entry)

            # Çok düşük fiyat uyarısı (penny stock risk)
            if price < 1.0:
                warnings.append(f"Düşük fiyatlı hisse (${price:.2f}) — likidite riski var")

        else:
            stop_levels = {"error": "aday verisi bulunamadı"}

        approved = len(veto_reasons) == 0

        return {
            "approved": approved,
            "veto_reasons": veto_reasons,
            "warnings": warnings,
            "adjusted_budget_pct": round(budget_multiplier, 2),
            "stop_levels": stop_levels,
        }
