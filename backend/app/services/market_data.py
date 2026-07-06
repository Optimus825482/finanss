"""
Watchlist ve portföy için ortak canlı fiyat servisi.
Araştırma pipeline'ındaki ScannerAgent'tan bağımsız, hafif ve tek amaçlı.
"""
import yfinance as yf


def get_live_prices(tickers: list[str]) -> dict[str, dict]:
    """Her ticker için {price, change_pct} döner. Veri çekilemeyen semboller
    None olarak işaretlenir, hiçbir zaman exception fırlatmaz."""
    result: dict[str, dict] = {}
    unique = list(dict.fromkeys(t for t in tickers if t))
    if not unique:
        return result

    try:
        data = yf.download(
            unique, period="5d", interval="1d",
            group_by="ticker", threads=True, progress=False,
        )
    except Exception:
        data = None

    for t in unique:
        try:
            if data is None:
                raise ValueError("veri yok")
            hist = data[t] if len(unique) > 1 else data
            hist = hist.dropna()
            if hist.empty:
                result[t] = {"price": None, "change_pct": None}
                continue
            last = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last
            change_pct = ((last - prev) / prev * 100) if prev else 0.0
            result[t] = {"price": round(last, 2), "change_pct": round(change_pct, 2)}
        except Exception:
            result[t] = {"price": None, "change_pct": None}

    return result
