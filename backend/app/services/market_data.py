"""
Watchlist ve portföy için ortak canlı fiyat servisi.
Araştırma pipeline'ındaki ScannerAgent'tan bağımsız, hafif ve tek amaçlı.
"""
import pandas as pd
import yfinance as yf


def get_live_prices(tickers: list[str]) -> dict[str, dict]:
    """Her ticker için {price, change_pct} döner. Veri çekilemeyen semboller
    None olarak işaretlenir, hiçbir zaman exception fırlatmaz."""
    result: dict[str, dict] = {}
    unique = list(dict.fromkeys(t for t in tickers if t))
    if not unique:
        return result

    try:
        # yfinance >= 1.0: group_by kalktı, multi-ticker her zaman
        # MultiIndex column (Price, Ticker) döner.
        data = yf.download(
            unique, period="5d", interval="1d",
            progress=False,
        )
    except Exception:
        data = None

    for t in unique:
        try:
            if data is None or data.empty:
                raise ValueError("veri yok")
            # Close kolonuna erişim: data['Close'] Series/DataFrame
            # tek sembolde Series, çoklu sembolde DataFrame döner.
            closes = data.get("Close", pd.DataFrame())
            if len(unique) == 1:
                if isinstance(closes, pd.DataFrame) and closes.shape[1] == 1:
                    closes = closes.iloc[:, 0]
            else:
                closes = closes[t] if t in closes.columns else None
                if closes is None:
                    result[t] = {"price": None, "change_pct": None}
                    continue
            closes = closes.dropna()
            if closes.empty:
                result[t] = {"price": None, "change_pct": None}
                continue
            last = float(closes.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) > 1 else last
            change_pct = ((last - prev) / prev * 100) if prev else 0.0
            result[t] = {"price": round(last, 2), "change_pct": round(change_pct, 2)}
        except Exception:
            result[t] = {"price": None, "change_pct": None}

    return result
