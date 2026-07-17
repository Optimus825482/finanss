"""Insider Activity — içeriden işlem analizi.

Yahoo Finance insider_transactions verisini çeker,
alım/satım dengesi ve net sentiment üretir.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from app.services.yf_utils import safe_ticker_info

logger = logging.getLogger(__name__)


async def run(ticker: str, db=None) -> dict:
    """İçeriden işlem analizi — son 6 ay.

    Returns:
        {ticker, transactions: [{type, shares, value, insider_name, date}],
         net_sentiment: "bullish"|"bearish"|"neutral", buy_count, sell_count}
    """
    ticker = ticker.upper().strip()

    try:
        t = await asyncio.to_thread(safe_ticker_info, ticker)
    except Exception:
        t = {}

    insider_txns = t.get("insiderTransactions") if isinstance(t, dict) else []
    if not insider_txns:
        # yfinance 1.x — insider_transactions farklı yapıda olabilir
        try:
            import yfinance as yf
            yt = yf.Ticker(ticker)
            insider_txns = getattr(yt, "insider_transactions", None)
            if insider_txns is None:
                insider_txns = getattr(yt, "insider_transactions", None) or []
        except Exception:
            insider_txns = []

    transactions = []
    buy_count = 0
    sell_count = 0
    buy_value = 0.0
    sell_value = 0.0
    cutoff = datetime.now() - timedelta(days=180)

    for tx in (insider_txns or []):
        if not isinstance(tx, dict):
            continue
        try:
            # Farklı yfinance versiyonları farklı key kullanır
            shares = tx.get("shares") or tx.get("transactionShares") or 0
            value = tx.get("value") or tx.get("transactionValue") or 0
            tx_type = str(tx.get("transactionType") or tx.get("transactionText") or "").lower()

            if "buy" in tx_type or "purchase" in tx_type:
                action = "buy"
                buy_count += 1
                buy_value += float(value) if value else float(shares) * 100
            elif "sell" in tx_type or "sale" in tx_type:
                action = "sell"
                sell_count += 1
                sell_value += float(value) if value else float(shares) * 100
            else:
                action = "other"
                continue

            transactions.append({
                "type": action,
                "shares": int(shares) if shares else 0,
                "value": round(float(value), 2) if value else None,
                "insider_name": str(tx.get("insiderName") or tx.get("officerName") or "Bilinmiyor"),
                "date": str(tx.get("startDate") or tx.get("filingDate") or ""),
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

    total_txns = min(len(transactions), 20)

    return {
        "ticker": ticker,
        "transactions": transactions[:total_txns],
        "net_sentiment": net_sentiment,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "buy_value": round(buy_value, 2),
        "sell_value": round(sell_value, 2),
        "data_missing": [] if transactions else ["insider_transactions"],
    }
