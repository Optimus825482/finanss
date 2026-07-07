"""
Qlib tarzi factor expression engine — numpy tabanli teknik gosterge hesaplamalari.
TA-Lib bagimliligi yok, saf Python/NumPy.
"""
import numpy as np


class FactorEngine:
    """Qlib'in factor expression engine'inden esinlenildi."""

    @staticmethod
    def sma(arr: np.ndarray, period: int) -> np.ndarray:
        """Basit hareketli ortalama."""
        out = np.full(len(arr), np.nan)
        if len(arr) < period:
            return out
        cumsum = np.cumsum(np.insert(arr, 0, 0))
        out[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
        return out

    @staticmethod
    def ema(arr: np.ndarray, period: int) -> np.ndarray:
        """Ussel hareketli ortalama."""
        out = np.full(len(arr), np.nan)
        if len(arr) < 2:
            return out
        k = 2.0 / (period + 1)
        out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = arr[i] * k + out[i - 1] * (1 - k)
        return out

    @staticmethod
    def rsi(arr: np.ndarray, period: int = 14) -> np.ndarray:
        """Goreceli Gu Endeksi (RSI)."""
        out = np.full(len(arr), np.nan)
        if len(arr) < period + 1:
            return out
        delta = np.diff(arr)
        gains = np.where(delta > 0, delta, 0.0)
        losses = np.where(delta < 0, -delta, 0.0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        out[period] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss)) if avg_loss > 0 else 100.0

        for i in range(period + 1, len(arr)):
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
            out[i] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss)) if avg_loss > 0 else 100.0
        return out

    @staticmethod
    def macd(arr: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """MACD: {macd, signal, histogram}."""
        ema_fast = FactorEngine.ema(arr, fast)
        ema_slow = FactorEngine.ema(arr, slow)
        macd_line = ema_fast - ema_slow
        signal_line = FactorEngine.ema(macd_line[~np.isnan(macd_line)], signal)
        # signal'i orijinal boyuta padle
        pad_len = len(arr) - len(signal_line)
        signal_line = np.concatenate([np.full(pad_len, np.nan), signal_line])
        histogram = macd_line - signal_line
        return {"macd": macd_line.tolist(), "signal": signal_line.tolist(), "histogram": histogram.tolist()}

    @staticmethod
    def bollinger(arr: np.ndarray, period: int = 20, std_mult: float = 2.0) -> dict:
        """Bollinger Bantlari."""
        middle = FactorEngine.sma(arr, period)
        stds = np.full(len(arr), np.nan)
        for i in range(period - 1, len(arr)):
            stds[i] = np.std(arr[i - period + 1: i + 1])
        upper = middle + std_mult * stds
        lower = middle - std_mult * stds
        return {"upper": upper.tolist(), "middle": middle.tolist(), "lower": lower.tolist()}

    @staticmethod
    def volatility(arr: np.ndarray, window: int = 20, annualize: int = 252) -> np.ndarray:
        """Yilliklandirilmis volatilite."""
        log_returns = np.log(arr[1:] / arr[:-1])
        out = np.full(len(arr), np.nan)
        for i in range(window - 1, len(log_returns)):
            out[i + 1] = np.std(log_returns[i - window + 1: i + 1]) * np.sqrt(annualize)
        return out

    @staticmethod
    def max_drawdown(arr: np.ndarray) -> float:
        """Maksimum dusus yuzdesi."""
        peak = np.maximum.accumulate(arr)
        drawdown = (arr - peak) / peak
        return float(np.min(drawdown)) if len(arr) > 0 else 0.0

    @staticmethod
    def beta(stock_returns: np.ndarray, benchmark_returns: np.ndarray) -> float:
        """Beta katsayisi."""
        if len(stock_returns) < 5 or len(benchmark_returns) < 5:
            return 0.0
        common = min(len(stock_returns), len(benchmark_returns))
        s = stock_returns[-common:]
        b = benchmark_returns[-common:]
        mask = ~(np.isnan(s) | np.isnan(b))
        if mask.sum() < 5:
            return 0.0
        cov = np.cov(s[mask], b[mask])
        var_b = np.var(b[mask])
        return float(cov[0][1] / var_b) if var_b > 0 else 0.0

    @staticmethod
    def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Yilliklandirilmis Sharpe orani."""
        excess = returns - risk_free_rate / 252
        if len(excess) < 2:
            return 0.0
        return float(np.mean(excess) / np.std(excess) * np.sqrt(252)) if np.std(excess) > 0 else 0.0


def compute_all_technicals(closes: list[float], volumes: list[float] | None = None) -> dict:
    """Bir hisse icin tum teknik gostergeleri hesapla (Qlib formatinda)."""
    engine = FactorEngine()
    arr = np.array(closes, dtype=np.float64)

    result = {
        "sma_20": engine.sma(arr, 20).tolist(),
        "sma_50": engine.sma(arr, 50).tolist(),
        "sma_200": engine.sma(arr, 200).tolist(),
        "ema_20": engine.ema(arr, 20).tolist(),
        "rsi_14": engine.rsi(arr, 14).tolist(),
        "macd": engine.macd(arr),
        "bollinger": engine.bollinger(arr),
        "volatility_20": engine.volatility(arr, 20).tolist(),
        "max_drawdown": engine.max_drawdown(arr),
    }

    if volumes:
        vol_arr = np.array(volumes, dtype=np.float64)
        result["avg_volume_20"] = np.mean(vol_arr[-20:]) if len(vol_arr) >= 20 else float(np.mean(vol_arr))

    return result
