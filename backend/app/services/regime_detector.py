"""
Market Regime Detector — Makro verilerden piyasa rejimi sınıflandırması.

3 rejim:
- bull (≥70): risk-on, momentum ağırlıklı strateji
- neutral (30-70): dengeli, normal pozisyon büyüklüğü
- bear (≤30): risk-off, savunma/short strateji

Göstergeler:
- VIX (korku endeksi): >25 = bearish
- 10Y Tahvil faizi trendi
- S&P500 20 günlük momentum
- Dolar endeksi trendi
- Altın momentumu (safe-haven akışı)
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

from app.services.yf_utils import safe_download
from app.services.market_data import MACRO_INDICATORS

logger = logging.getLogger(__name__)

# Regime thresholds
BULL_THRESHOLD = 70
BEAR_THRESHOLD = 30
VIX_FEAR = 25.0
MOMENTUM_WINDOW = 20


class RegimeDetector:
    """Makro göstergelerden piyasa rejimi tespit eder."""

    def __init__(self):
        self._cache: Optional[dict] = None
        self._cache_time = None

    def detect(self) -> dict:
        """Piyasa rejimini tespit et — sonuç cache'lenir (tek seferlik çağrı)."""
        import time
        now = time.time()
        if self._cache is not None and self._cache_time and (now - self._cache_time) < 300:
            return self._cache

        result = self._compute()
        self._cache = result
        self._cache_time = now
        return result

    def _compute(self) -> dict:
        """Tüm makro göstergeleri çekip rejim skoru hesapla."""
        scores = {}
        details = {}

        # 1. VIX — korku endeksi
        try:
            vix_data = safe_download(["^VIX"], period="1mo", interval="1d", progress=False)
            if vix_data is not None and not vix_data.empty:
                vix_close = vix_data["Close"]
                if isinstance(vix_close, pd.DataFrame):
                    vix_val = float(vix_close.iloc[-1].iloc[0]) if vix_close.shape[1] > 0 else None
                else:
                    vix_val = float(vix_close.iloc[-1])
                if vix_val:
                    if vix_val > 30:
                        scores["vix"] = 10   # extreme fear
                    elif vix_val > VIX_FEAR:
                        scores["vix"] = 25   # fear
                    elif vix_val > 18:
                        scores["vix"] = 65   # normal
                    elif vix_val > 13:
                        scores["vix"] = 80   # calm
                    else:
                        scores["vix"] = 95   # extremely calm
                    details["vix"] = round(vix_val, 2)
        except Exception as e:
            logger.debug("VIX fetch failed: %s", e)

        # 2. S&P500 20-gün momentum
        try:
            spx = safe_download(["^GSPC"], period="3mo", interval="1d", progress=False)
            if spx is not None and not spx.empty:
                closes = spx["Close"]
                if isinstance(closes, pd.DataFrame):
                    closes = closes.iloc[:, 0]
                closes = closes.dropna()
                if len(closes) > MOMENTUM_WINDOW:
                    mom_20 = (float(closes.iloc[-1]) / float(closes.iloc[-MOMENTUM_WINDOW]) - 1) * 100
                    if mom_20 > 5:
                        scores["spx_momentum"] = 85
                    elif mom_20 > 0:
                        scores["spx_momentum"] = 65
                    elif mom_20 > -5:
                        scores["spx_momentum"] = 35
                    else:
                        scores["spx_momentum"] = 15
                    details["spx_momentum_20d"] = round(mom_20, 2)
        except Exception as e:
            logger.debug("S&P500 fetch failed: %s", e)

        # 3. Dolar Endeksi trendi
        try:
            dxy = safe_download(["DX-Y.NYB"], period="3mo", interval="1d", progress=False)
            if dxy is not None and not dxy.empty:
                closes = dxy["Close"]
                if isinstance(closes, pd.DataFrame):
                    closes = closes.iloc[:, 0]
                closes = closes.dropna()
                if len(closes) > MOMENTUM_WINDOW:
                    mom_20 = (float(closes.iloc[-1]) / float(closes.iloc[-MOMENTUM_WINDOW]) - 1) * 100
                    # Güçlü dolar → EM baskı → BIST için bearish
                    if mom_20 > 2:
                        scores["dollar"] = 25
                    elif mom_20 > 0:
                        scores["dollar"] = 40
                    else:
                        scores["dollar"] = 70  # zayıf dolar → EM olumlu
                    details["dxy_momentum_20d"] = round(mom_20, 2)
        except Exception as e:
            logger.debug("DXY fetch failed: %s", e)

        # 4. Altın momentumu (safe-haven akışı)
        try:
            gold = safe_download(["GC=F"], period="2mo", interval="1d", progress=False)
            if gold is not None and not gold.empty:
                closes = gold["Close"]
                if isinstance(closes, pd.DataFrame):
                    closes = closes.iloc[:, 0]
                closes = closes.dropna()
                if len(closes) > MOMENTUM_WINDOW:
                    mom_20 = (float(closes.iloc[-1]) / float(closes.iloc[-MOMENTUM_WINDOW]) - 1) * 100
                    # Altın yükseliyor → risk-off → bearish
                    if mom_20 > 3:
                        scores["gold"] = 25
                    elif mom_20 > 0:
                        scores["gold"] = 40
                    else:
                        scores["gold"] = 70
                    details["gold_momentum_20d"] = round(mom_20, 2)
        except Exception as e:
            logger.debug("Gold fetch failed: %s", e)

        # 5. 10Y Tahvil Faizi
        try:
            tnote = safe_download(["^TNX"], period="2mo", interval="1d", progress=False)
            if tnote is not None and not tnote.empty:
                closes = tnote["Close"]
                if isinstance(closes, pd.DataFrame):
                    closes = closes.iloc[:, 0]
                closes = closes.dropna()
                if len(closes) > MOMENTUM_WINDOW:
                    current = float(closes.iloc[-1])
                    prev = float(closes.iloc[-MOMENTUM_WINDOW])
                    mom_20 = (current / prev - 1) * 100
                    # Yükselen faiz → risk-off (tahvil fiyatı düşer)
                    if mom_20 > 5:
                        scores["rates"] = 20
                    elif mom_20 > 0:
                        scores["rates"] = 40
                    else:
                        scores["rates"] = 70
                    details["tnx_yield"] = round(current, 2)
                    details["tnx_momentum_20d"] = round(mom_20, 2)
        except Exception as e:
            logger.debug("TNX fetch failed: %s", e)

        # Composited score
        if scores:
            regime_score = round(sum(scores.values()) / len(scores), 1)
        else:
            regime_score = 50.0

        if regime_score >= BULL_THRESHOLD:
            regime = "bull"
        elif regime_score <= BEAR_THRESHOLD:
            regime = "bear"
        else:
            regime = "neutral"

        return {
            "regime": regime,
            "regime_score": regime_score,
            "details": details,
            "indicators_used": len(scores),
        }
