"""
Kelly Position Sizing — Fractional Kelly Criterion.

Formula:  K% = W - [(1 - W) / R]
- W = win rate (last N trades)
- R = risk-reward ratio (avg_win / avg_loss)
- Fraction: half-Kelly (0.5) for safety, floor 1%, ceiling per config

Uses trailing 30-trade window from TradingDecision table.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.core import TradingDecision

logger = logging.getLogger(__name__)

# Kelly defaults
DEFAULT_WINDOW = 30       # trailing trades for win-rate estimation
MIN_WINDOW = 8            # minimum trades before Kelly activates
FRACTION = 0.5            # half-Kelly (conservative)
FLOOR_PCT = 0.01          # 1% minimum position
CEILING_PCT = 0.25        # 25% maximum position (mirrors max_per_position_pct)


def kelly_position_size(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float:
    """Pure Kelly formula: K% = W - [(1-W)/R]."""
    if avg_loss <= 0 or win_rate <= 0:
        return 0.0
    R = avg_win / avg_loss
    kelly = win_rate - (1.0 - win_rate) / R
    return max(0.0, kelly)


def fractional_kelly(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fraction: float = FRACTION,
    floor: float = FLOOR_PCT,
    ceiling: float = CEILING_PCT,
) -> float:
    """Half-Kelly with safety bounds."""
    full = kelly_position_size(win_rate, avg_win, avg_loss)
    fractional = full * fraction
    return max(floor, min(ceiling, fractional))


def compute_win_metrics(
    db: Session,
    portfolio_id: int,
    window: int = DEFAULT_WINDOW,
) -> dict:
    """Calculate win rate + avg win/loss from last N trading decisions.

    A "win" = sell trade where the position closed with positive P/L.
    """
    decisions = (
        db.query(TradingDecision)
        .filter(TradingDecision.portfolio_id == portfolio_id)
        .order_by(TradingDecision.created_at.desc())
        .limit(window * 3)  # oversample to get enough sells
        .all()
    )

    # Extract closed trades: buy→sell pairs (same ticker, same position context)
    # Simpler approach: use the sell decisions' implied P/L from portfolio_value delta
    sells = [d for d in decisions if d.action == "sell"]
    if not sells or len(sells) < 2:
        return {"win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "trade_count": 0, "ready": False}

    # For each sell, estimate P/L: if portfolio_value_after > portfolio_value_before = win
    wins = 0
    win_amounts = []
    loss_amounts = []
    for s in sells[:window]:
        try:
            # Find the matching buy to calculate actual P/L
            buy = (
                db.query(TradingDecision)
                .filter(
                    TradingDecision.ticker == s.ticker,
                    TradingDecision.portfolio_id == portfolio_id,
                    TradingDecision.action == "buy",
                    TradingDecision.created_at < s.created_at,
                )
                .order_by(TradingDecision.created_at.desc())
                .first()
            )
            if buy and s.price and buy.price:
                pl = (s.price - buy.price) * s.quantity
                if pl > 0:
                    wins += 1
                    win_amounts.append(abs(pl))
                elif pl < 0:
                    loss_amounts.append(abs(pl))
        except Exception:
            pass

    # Fallback: if no buy-sell pairs found, use portfolio value delta
    if wins == 0 and len(win_amounts) == 0 and len(loss_amounts) == 0:
        # Use portfolio value before/after deltas
        for s in sells[:window]:
            if s.portfolio_value_before and s.portfolio_value_after:
                delta = s.portfolio_value_after - s.portfolio_value_before
                if delta > 0:
                    wins += 1
                    win_amounts.append(delta)
                elif delta < 0:
                    loss_amounts.append(abs(delta))

    trade_count = wins + len(loss_amounts)
    win_rate = wins / trade_count if trade_count > 0 else 0.0
    avg_win = sum(win_amounts) / len(win_amounts) if win_amounts else 1.0
    avg_loss = sum(loss_amounts) / len(loss_amounts) if loss_amounts else 1.0

    return {
        "win_rate": round(win_rate, 3),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "trade_count": trade_count,
        "ready": trade_count >= MIN_WINDOW,
    }


def get_position_budget(
    db: Session,
    portfolio_id: int,
    cash: float,
    default_pct: float = 0.10,
) -> float:
    """Get single-position budget using fractional Kelly.

    Falls back to default_pct when not enough trade history.
    """
    metrics = compute_win_metrics(db, portfolio_id)
    if not metrics["ready"]:
        logger.debug("Kelly not ready (%d trades, need %d), using default %.0f%%",
                     metrics["trade_count"], MIN_WINDOW, default_pct * 100)
        return cash * default_pct

    kelly = fractional_kelly(
        metrics["win_rate"],
        metrics["avg_win"],
        metrics["avg_loss"],
    )
    budget = cash * kelly
    logger.info(
        "Kelly sizing: win_rate=%.1f%% avg_win=$%.2f avg_loss=$%.2f kelly=%.1f%% budget=$%.2f (trades=%d)",
        metrics["win_rate"] * 100, metrics["avg_win"], metrics["avg_loss"],
        kelly * 100, budget, metrics["trade_count"],
    )
    return budget


def adjust_for_regime(budget: float, regime_score: float) -> float:
    """Piyasa rejimine göre pozisyon bütçesini ayarla.

    regime_score: 0-100 (0=bear, 50=neutral, 100=bull)
    Bear piyasada %50 küçült, bull'da %20 büyüt.
    """
    if regime_score <= 30:
        # Bear: shrink positions
        multiplier = 0.5
    elif regime_score >= 70:
        # Bull: expand slightly
        multiplier = 1.2
    else:
        multiplier = 1.0
    return budget * multiplier
