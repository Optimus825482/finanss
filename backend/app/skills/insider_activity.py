"""Insider Activity — içeriden işlem analizi.

Yahoo Finance insider_transactions property'sini kullanır
(.info dict'inde gelmez — ayrı property).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def run(ticker: str, db=None) -> dict:
    """İçeriden işlem analizi — son 6 ay.

    Returns:
        {ticker, transactions: [{type, shares, value, insider_name, date}],
         net_sentiment: "bullish"|"bearish"|"neutral", buy_count, sell_count}
    """
    ticker = ticker.upper().strip()

    insider_txns = []
    try:
        import yfinance as yf
        from app.services.yf_utils import with_retry

        def _fetch():
            yt = yf.Ticker(ticker)
            # insider_transactions yfinance'de ayrı bir property
            txns = getattr(yt, "insider_transactions", None)
            if txns is None:
                txns = getattr(yt, "insider_transactions", None)
            return txns or []

        insider_txns = await asyncio.to_thread(lambda: with_retry(_fetch, retries=2))
    except Exception as e:
        logger.warning("insider fetch failed for %s: %s", ticker, e)

    if not isinstance(insider_txns, (list, dict)):
        insider_txns = []

    transactions = []
    buy_count = 0
    sell_count = 0
    buy_value = 0.0
    sell_value = 0.0

    # yfinance insider_transactions farklı formatlarda gelebilir
    items = insider_txns if isinstance(insider_txns, list) else insider_txns.get("transactions", [])

    for tx in items:
        if not isinstance(tx, dict):
            continue
        try:
            shares = tx.get("shares") or tx.get("transactionShares") or 0
            value = tx.get("value") or tx.get("transactionValue") or 0
            tx_type = str(tx.get("transactionType") or tx.get("transactionText") or tx.get("filingType") or "").lower()

            if "buy" in tx_type or "purchase" in tx_type or "acquisition" in tx_type:
                action = "buy"
                buy_count += 1
                buy_value += float(value) if value else float(shares) * 100
            elif "sell" in tx_type or "sale" in tx_type or "disposition" in tx_type:
                action = "sell"
                sell_count += 1
                sell_value += float(value) if value else float(shares) * 100
            else:
                continue  # award/option exercise etc -> skip

            transactions.append({
                "type": action,
                "shares": int(float(shares)) if shares else 0,
                "value": round(float(value), 2) if value else None,
                "insider_name": str(tx.get("insiderName") or tx.get("officerName") or tx.get("reportingPerson", {}).get("name", "") or "Bilinmiyor"),
                "date": str(tx.get("startDate") or tx.get("filingDate") or tx.get("transactionDate") or ""),
            })
        except Exception:
            continue

    # Net sentiment
    if buy_count > sell_count * 1.5:
        net_sentiment = "bullish"
    elif sell_count > buy_count * 1.5:
        net_sentiment = "bearish"
    else:
        net_sentiment = "neutral"

    return {
        "ticker": ticker,
        "transactions": transactions[:20],
        "net_sentiment": net_sentiment,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "buy_value": round(buy_value, 2),
        "sell_value": round(sell_value, 2),
        "data_missing": [] if transactions else ["insider_transactions"],
    }
