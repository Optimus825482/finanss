"""Binance public API servisi — ücretsiz, API key gerektirmez.

Kapsam: M5 klines (mum) çekme + canlı fiyat. Tüm uçlar public `/api/v3`:
- klines: https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=500
- price:  https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT

Rate-limit: Binance 1 dk'da ~6000 istek (IP bazlı) — in-memory cache + min
istek stratejisi yeterli. Kripto 7/24 açık, yfinance'a bağımlılık yok.

Hata durumu: None / boş liste döner (caller graceful handle eder).
"""
import json
import logging
import time
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

_API = "https://api.binance.com/api/v3"
_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"}
_MAX_LIMIT = 1000

# In-memory cache: {url: (ts, data)} — 30s TTL fiyat, 60s TTL klines
_price_cache: dict[str, tuple[float, Optional[dict]]] = {}
_kline_cache: dict[str, tuple[float, list]] = {}
_PRICE_TTL = 30
_KLINE_TTL = 60

_UA = "Mozilla/5.0 (OrbisFinaiCrypto/1.0)"


def _get(url: str, timeout: float = 10.0):
    """GET isteği — JSON döner, hata durumunda None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        logger.warning("Binance GET failed %s: %s", url, e)
        return None


def get_price(symbol: str) -> Optional[dict]:
    """Canlı fiyat: {price, change_pct (5m)} — 30s cache."""
    symbol = symbol.upper().strip()
    now = time.time()
    cached = _price_cache.get(symbol)
    if cached and now - cached[0] < _PRICE_TTL:
        return cached[1]

    # Fiyat + 5m önceki fiyat (change_pct için)
    px = _get(f"{_API}/ticker/price?symbol={symbol}")
    if px is None or px.get("price") is None:
        return None
    price = float(px["price"])

    # Önceki 5m fiyatı: son kline'ın open'ı ≈ 5m önceki fiyat
    klines = get_klines(symbol, "5m", limit=2)
    prev = float(klines[0]["open"]) if klines and len(klines) >= 2 else price
    change_pct = round((price - prev) / prev * 100, 4) if prev > 0 else 0.0

    result = {"symbol": symbol, "price": price, "change_pct": change_pct}
    _price_cache[symbol] = (now, result)
    return result


def get_klines(symbol: str, interval: str = "5m", limit: int = 200) -> list:
    """Binance klines (mum) — OHLCV listesi.

    Returns: [{open_time, open, high, low, close, volume, close_time}, ...]
    Hata/geçersiz interval → [] (caller handle eder).
    """
    symbol = symbol.upper().strip()
    if interval not in _INTERVALS:
        logger.warning("Geçersiz interval: %s (geçerli: %s)", interval, sorted(_INTERVALS))
        return []
    limit = max(1, min(limit, _MAX_LIMIT))

    cache_key = f"{symbol}:{interval}:{limit}"
    now = time.time()
    cached = _kline_cache.get(cache_key)
    if cached and now - cached[0] < _KLINE_TTL:
        return cached[1]

    raw = _get(f"{_API}/klines?symbol={symbol}&interval={interval}&limit={limit}")
    if raw is None or not isinstance(raw, list) or not raw:
        return []

    # Binance klines formatı:
    # [0]=open_time ms, [1]=open, [2]=high, [3]=low, [4]=close,
    # [5]=volume, [6]=close_time ms, ...
    rows = []
    for k in raw:
        try:
            rows.append({
                "open_time": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "close_time": int(k[6]),
            })
        except (IndexError, TypeError, ValueError):
            continue
    if rows:
        _kline_cache[cache_key] = (now, rows)
    return rows


def get_klines_df(symbol: str, interval: str = "5m", limit: int = 200):
    """Klines'ı pandas DataFrame olarak döndür (analiz için). Boşsa None."""
    import pandas as pd
    rows = get_klines(symbol, interval, limit)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("date")
    return df


def ping() -> bool:
    """Binance API erişilebilir mi (health check)."""
    r = _get(f"{_API}/ping", timeout=5)
    return r == {}
