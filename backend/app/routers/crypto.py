"""Crypto API uçları — Binance M5 fiyat + klines + analiz.

Ücretsiz public API (key gerektirmez). Kripto 7/24 açık.
"""
import logging

from fastapi import APIRouter, HTTPException, Query

from app.config import CRYPTO_UNIVERSE
from app.services.binance_service import get_price, get_klines, ping
from app.services.screener_service import get_universe

router = APIRouter(prefix="/api/crypto", tags=["crypto"])
logger = logging.getLogger(__name__)


@router.get("/ping")
def api_ping():
    """Binance API erişilebilir mi."""
    return {"ok": ping()}


@router.get("/universe")
def api_universe():
    """Kripto evreni (Binance sembolleri)."""
    return {"count": len(CRYPTO_UNIVERSE), "symbols": CRYPTO_UNIVERSE}


@router.get("/price/{symbol}")
def api_price(symbol: str):
    """Canlı fiyat + 5m değişim."""
    px = get_price(symbol)
    if px is None:
        raise HTTPException(status_code=404, detail=f"{symbol} fiyatı alınamadı")
    return px


@router.get("/klines/{symbol}")
def api_klines(symbol: str, interval: str = Query("5m"), limit: int = Query(100, le=1000)):
    """M5 (veya diğer) mum verisi — OHLCV."""
    rows = get_klines(symbol, interval, limit)
    if not rows:
        raise HTTPException(status_code=404, detail=f"{symbol} klines alınamadı")
    return {"symbol": symbol.upper(), "interval": interval,
            "count": len(rows), "klines": rows}


@router.get("/analyze/{symbol}")
async def api_analyze(symbol: str, interval: str = Query("5m")):
    """Tek kripto M5 teknik analiz — CryptoAgent sinyali."""
    from app.agents.crypto_agent import compute_crypto_signal
    klines = get_klines(symbol, interval, limit=100)
    if not klines:
        raise HTTPException(status_code=404, detail=f"{symbol} verisi alınamadı")
    sig = compute_crypto_signal(klines)
    px = get_price(symbol)
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "price": (px or {}).get("price"),
        "change_pct": (px or {}).get("change_pct"),
        **sig,
        "last_klines": klines[-5:],
    }


@router.get("/scan")
async def api_scan(interval: str = Query("5m")):
    """Tüm evreni M5 tara → sinyal skoruna göre sırala."""
    from app.agents.crypto_agent import CryptoAgent
    tickers = get_universe(["CRYPTO"])
    candidates = []
    for sym in tickers:
        px = get_price(sym)
        if px:
            candidates.append({"ticker": sym, "price": px["price"],
                               "momentum_pct": px.get("change_pct", 0) or 0})
    if not candidates:
        return {"symbols_scanned": 0, "candidates": []}
    out = await CryptoAgent().run(candidates)
    out.sort(key=lambda c: c.get("composite_score", 50), reverse=True)
    return {"symbols_scanned": len(candidates), "candidates": out[:10]}


# ── Scalper (24/7 otonom döngü) ──

@router.post("/scalp/start")
def api_scalp_start():
    """Scalper döngüsünü başlat — idempotent."""
    from app.services.crypto_scalper import start
    return start()


@router.post("/scalp/stop")
def api_scalp_stop():
    """Scalper döngüsünü durdur."""
    from app.services.crypto_scalper import stop
    return stop()


@router.get("/scalp/status")
def api_scalp_status():
    """Scalper durumu + son tur bilgisi (frontend 1s polling)."""
    from app.services.crypto_scalper import status
    return status()


@router.get("/scalp/cards")
def api_scalp_cards():
    """Kural bazlı AL/HOLD/SELL kartları — her sembol için canlı sinyal + kural sonucu."""
    from app.services.crypto_scalper import cards
    return cards()
