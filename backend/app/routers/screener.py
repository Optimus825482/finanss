from fastapi import APIRouter, HTTPException, Query, Request
import math

import yfinance as yf

router = APIRouter(prefix="/api/screener", tags=["screener"])


def _sanitize(obj):
    """NaN/Infinity float'ları None yap (JSON uyumlu)."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


@router.get("/suggest")
def suggest_tickers(q: str):
    """Yahoo Finance benzeri hisse senedi arama/autocomplete."""
    if len(q) < 1:
        return []

    try:
        search = yf.Search(q.strip())
        results = []

        if search.quotes:
            for row in search.quotes[:12]:
                ticker = row.get("symbol", "")
                if not ticker:
                    continue
                results.append({
                    "ticker": ticker,
                    "name": row.get("shortname") or row.get("longname") or ticker,
                    "exchange": row.get("exchange", ""),
                    "exchange_name": row.get("exchDisp") or row.get("fullExchangeName") or row.get("exchange", ""),
                    "type": row.get("quoteType", "Equity"),
                    "sector": row.get("sector") or row.get("sectorDisp") or "",
                    "industry": row.get("industry") or row.get("industryDisp") or "",
                })

        valid_types = {"equity", "etf", "index", "currency", "future"}
        results = [r for r in results if r["type"].lower() in valid_types]
        return results[:10]
    except Exception:
        return []


@router.get("/{ticker}")
async def get_ticker_detail(ticker: str, period: str = Query("1mo"), interval: str = Query("1d")):
    """Hisse detayi: fiyat, sirket bilgisi, haberler, metrikler. Tum metinler Turkce."""
    from app.services.translation_service import (
        translate_sector, translate_country, translate_text, translate_batch,
    )

    ticker_str = ticker.strip().upper()
    try:
        t = yf.Ticker(ticker_str)
        info = t.info or {}

        sector_en = info.get("sector") or info.get("sectorDisp") or ""
        industry_en = info.get("industry") or info.get("industryDisp") or ""
        country_en = info.get("country") or ""
        description_en = info.get("longBusinessSummary") or ""

        sector_tr = translate_sector(sector_en)
        industry_tr = translate_sector(industry_en) if industry_en != sector_en else sector_tr
        country_tr = translate_country(country_en)

        result = {
            "ticker": ticker_str,
            "name": info.get("shortName") or info.get("longName") or ticker_str,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "change_pct": info.get("regularMarketChangePercent"),
            "change": info.get("regularMarketChange"),
            "previous_close": info.get("regularMarketPreviousClose"),
            "open": info.get("regularMarketOpen"),
            "day_high": info.get("regularMarketDayHigh"),
            "day_low": info.get("regularMarketDayLow"),
            "volume": info.get("regularMarketVolume"),
            "avg_volume": info.get("averageVolume"),
            "market_cap": info.get("marketCap"),
            "sector": sector_tr or sector_en,
            "sector_en": sector_en,
            "industry": industry_tr or industry_en,
            "industry_en": industry_en,
            "exchange": info.get("exchange", ""),
            "exchange_name": info.get("exchDisp") or info.get("fullExchangeName") or info.get("exchange", ""),
            "currency": info.get("currency", "USD"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "pb_ratio": info.get("priceToBook"),
            "eps": info.get("trailingEps"),
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "dividend_yield": info.get("dividendYield"),
            "revenue_growth": info.get("revenueGrowth"),
            "beta": info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "fifty_day_avg": info.get("fiftyDayAverage"),
            "two_hundred_day_avg": info.get("twoHundredDayAverage"),
            "description": await translate_text(description_en) if description_en else "",
            "description_en": description_en,
            "website": info.get("website", ""),
            "country": country_tr or country_en,
            "country_en": country_en,
            "employees": info.get("fullTimeEmployees"),
        }

        try:
            news_raw = t.news[:6] if t.news else []
            titles_en = [
                n.get("content", {}).get("title") or n.get("title", "")
                for n in news_raw
            ]
            titles_tr = await translate_batch(titles_en) if titles_en else []
            result["news"] = [
                {
                    "title": titles_tr[i] if i < len(titles_tr) else titles_en[i],
                    "title_en": titles_en[i],
                    "link": news_raw[i].get("content", {}).get("canonicalUrl", {}).get("url") or news_raw[i].get("link", ""),
                    "publisher": news_raw[i].get("content", {}).get("provider", {}).get("displayName", ""),
                    "published": news_raw[i].get("content", {}).get("pubDate", ""),
                }
                for i in range(len(news_raw))
            ]
        except Exception:
            result["news"] = []

        try:
            # intraday için max period sınırlı
            intraday_intervals = {"1m", "3m", "5m", "15m", "30m", "1h", "4h"}
            if interval in intraday_intervals:
                valid_periods = {"1d", "5d", "1mo", "3mo", "6mo", "1y"}
                if period not in valid_periods:
                    period = "1mo"

            hist = t.history(period=period, interval=interval)
            hist.index = hist.index.tz_localize(None)
            result["price_history"] = [
                {
                    "date": str(idx.date()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                }
                for idx, row in hist.iterrows()
            ][-30:]
        except Exception:
            result["price_history"] = []

        return _sanitize(result)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Sembol verisi alinamadi: {str(e)}")


@router.get("/{ticker}/fair-value")
def get_fair_value(ticker: str):
    """Adil deger hesaplama: Graham, DCF, Peter Lynch, PE karsilastirmasi ensemble."""
    from app.services.fair_value import calculate_fair_value
    try:
        return calculate_fair_value(ticker.strip().upper())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Adil deger hesaplanamadi: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Sembol verisi alinamadi: {str(e)}")
