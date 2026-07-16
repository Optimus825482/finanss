"""
yfinance rate-limit koruması: exponential backoff + retry wrapper.

Yahoo Finance resmi olmayan API'si ara sıra rate-limit veya geçici hata döner.
Bu modül tüm yfinance çağrı noktalarında kullanılır.
"""
import io
import logging
import time
import contextlib
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Suppress yfinance's stderr noise ("possibly delisted", "Failed download")
_YF_DEVNULL = contextlib.redirect_stderr(io.StringIO())


def with_retry(
    fn: Callable[..., T],
    *args: Any,
    retries: int = 3,
    backoff_base: float = 1.5,
    **kwargs: Any,
) -> T:
    """Sync yfinance çağrısı için exponential backoff + retry.

    Son denemede hata fırlatırsa — caller try/except ile handle etsin.
    """
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = backoff_base ** attempt
            logger.warning("yfinance retry %d/%d (%.1fs): %s", attempt + 1, retries, wait, e)
            time.sleep(wait)
    # unreachable — son deneme raise eder
    raise RuntimeError("with_retry: unreachable")


def safe_download(*args, retries: int = 3, **kwargs):
    """yf.download wrapper — hata durumunda None döner (caller None kontrolü yapar)."""
    import yfinance as yf
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return with_retry(yf.download, *args, retries=retries, **kwargs)
    except Exception as e:
        logger.warning("yf.download failed after %d retries: %s", retries, e)
        return None


def safe_ticker_info(ticker: str, retries: int = 3) -> dict:
    """yf.Ticker(ticker).info wrapper — hata durumunda {} döner."""
    import yfinance as yf
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return with_retry(lambda: yf.Ticker(ticker).info, retries=retries) or {}
    except Exception as e:
        logger.warning("yf.Ticker(%s).info failed: %s", ticker, e)
        return {}


def safe_ticker_history(ticker: str, period: str = "3mo", retries: int = 3, **kwargs):
    """yf.Ticker(ticker).history wrapper — hata durumunda empty DataFrame döner."""
    import yfinance as yf
    import pandas as pd
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return with_retry(yf.Ticker(ticker).history, period=period, retries=retries, **kwargs)
    except Exception as e:
        logger.warning("yf.Ticker(%s).history failed: %s", ticker, e)
        return pd.DataFrame()


def safe_ticker_news(ticker: str, retries: int = 3) -> list:
    """yf.Ticker(ticker).news wrapper — hata durumunda [] döner."""
    import yfinance as yf
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return with_retry(lambda: yf.Ticker(ticker).news or [], retries=retries)
    except Exception as e:
        logger.warning("yf.Ticker(%s).news failed: %s", ticker, e)
        return []


def safe_ticker_dividends(ticker: str, retries: int = 3):
    """yf.Ticker(ticker).dividends wrapper — hata durumunda empty Series döner.

    Temettü geçmişi (tarih -> ödeme). skills.dividend modülü için eklendi.
    """
    import yfinance as yf
    import pandas as pd
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return with_retry(lambda: yf.Ticker(ticker).dividends, retries=retries) or pd.Series(dtype=float)
    except Exception as e:
        logger.warning("yf.Ticker(%s).dividends failed: %s", ticker, e)
        return pd.Series(dtype=float)


def safe_ticker_financials(ticker: str, retries: int = 3):
    """yf.Ticker(ticker).financials wrapper — yıllık gelir tablosu. Hata → empty DataFrame."""
    import yfinance as yf
    import pandas as pd
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return with_retry(lambda: yf.Ticker(ticker).financials, retries=retries) or pd.DataFrame()
    except Exception as e:
        logger.warning("yf.Ticker(%s).financials failed: %s", ticker, e)
        return pd.DataFrame()


def safe_ticker_balance_sheet(ticker: str, retries: int = 3):
    """yf.Ticker(ticker).balance_sheet wrapper — yıllık bilanço. Hata → empty DataFrame."""
    import yfinance as yf
    import pandas as pd
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return with_retry(lambda: yf.Ticker(ticker).balance_sheet, retries=retries) or pd.DataFrame()
    except Exception as e:
        logger.warning("yf.Ticker(%s).balance_sheet failed: %s", ticker, e)
        return pd.DataFrame()


def safe_ticker_cashflow(ticker: str, retries: int = 3):
    """yf.Ticker(ticker).cashflow wrapper — yıllık nakit akışı. Hata → empty DataFrame.

    payout ratio = dividendsPaid / netIncome için skills.dividend kullanır.
    """
    import yfinance as yf
    import pandas as pd
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return with_retry(lambda: yf.Ticker(ticker).cashflow, retries=retries) or pd.DataFrame()
    except Exception as e:
        logger.warning("yf.Ticker(%s).cashflow failed: %s", ticker, e)
        return pd.DataFrame()
