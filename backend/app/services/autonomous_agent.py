"""
Otonom Trading Ajani (Autonomous Trading Agent)

Tum kararlari kendi veren, portfoy yoneten LLM destekli ajan.

Tools:
- scan_market: Tum evrenden yatirim firsati tara
- analyze_ticker: Bir hisseyi tum ajan pipeline'indan gecir
- get_portfolio_status: Mevcut portfoy durumu
- execute_buy: Alim yap
- execute_sell: Satis yap
- get_price: Anlik fiyat al
- get_predictions: Kayitli ongoruleri kontrol et

Her karar trading_decisions tablosuna loglanir.
"""
import asyncio
import json
from datetime import datetime
from typing import Optional

import yfinance as yf
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.core import PortfolioPosition
from app.models.balance import BalanceTransaction
from app.services.balance_service import get_balance, deposit, record_position_opened, record_position_closed
from app.services.market_data import get_live_prices
from app.services.memory_service import store_research_memory


# ── Agent Brain ──

class AutonomousAgent:
    """Tamamen otonom trading ajani. LLM karar verir, DB'ye loglar."""

    def __init__(self, model: str = "ensemble-light"):
        self.model = model
        self.max_positions = 8
        self.max_per_position_pct = 0.25  # max %25 bakiye tek hisseye
        self.min_confidence = 0.6      # bu guvenin altinda alim yapma

    @property
    def name(self) -> str:
        return "autonomous_agent"

    # ── Tools ──

    def get_market_status(self, exchanges: list[str] | None = None) -> dict:
        """Piyasa durumu: tum evrenden hizli teknik tarama."""
        from app.services.screener_service import stage1_prescreen, get_universe
        tickers = get_universe(exchanges)
        return asyncio.run(stage1_prescreen(tickers))  # sync wrapper for agent

    def analyze_single(self, ticker: str) -> dict:
        """Tek hisse detayli analiz (full agent pipeline)."""
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}
        hist = t.history(period="3mo")
        hist.index = hist.index.tz_localize(None)

        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        prev_close = info.get("regularMarketPreviousClose", price)
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0

        # Simple candidate
        candidate = {
            "ticker": ticker, "price": price,
            "momentum_pct": round(change_pct, 2),
            "volume_ratio": 1.0, "history": hist,
        }

        # Run agents
        async def _run():
            from app.agents.fundamental_agent import FundamentalAgent
            from app.agents.sentiment_agent import SentimentAgent
            from app.agents.risk_agent import RiskAgent
            from app.agents.report_agent import ReportAgent

            f = FundamentalAgent(); s = SentimentAgent(); r = RiskAgent(); rep = ReportAgent()
            c = await f.run([candidate])
            c = await s.run(c)
            c = await r.run(c)
            return c[0] if c else candidate

        return asyncio.run(_run())

    def get_portfolio(self, db: Session) -> dict:
        """Mevcut portfoy ve bakiye durumu."""
        balance = get_balance(db)
        positions = db.query(PortfolioPosition).filter(PortfolioPosition.status == "open").all()
        total_cost = sum(p.quantity * p.entry_price for p in positions)
        tickers = [p.ticker for p in positions]
        prices = get_live_prices(tickers) if tickers else {}
        total_market = 0
        for p in positions:
            px = prices.get(p.ticker, {}).get("price") or p.entry_price
            total_market += p.quantity * px

        return {
            "cash": balance.cash,
            "position_count": len(positions),
            "total_cost": round(total_cost, 2),
            "total_market_value": round(total_market, 2),
            "total_pl": round(total_market - total_cost, 2),
            "total_pl_pct": round((total_market - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0,
            "positions": [{
                "id": p.id, "ticker": p.ticker, "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": prices.get(p.ticker, {}).get("price"),
                "unrealized_pl": round(p.quantity * ((prices.get(p.ticker, {}).get("price") or p.entry_price) - p.entry_price), 2),
            } for p in positions],
        }

    def execute_buy(self, db: Session, ticker: str, quantity: float, price: float, reasoning: str, portfolio_before: dict, confidence: float = 0.7) -> dict:
        """Alim yap."""
        balance = get_balance(db)
        total_cost = round(quantity * price, 2)
        if balance.cash < total_cost:
            return {"success": False, "error": f"Yetersiz bakiye. Gereken: ${total_cost}, Mevcut: ${balance.cash}"}

        pos = PortfolioPosition(ticker=ticker.upper(), quantity=quantity, entry_price=price,
                                entry_date=datetime.utcnow(), status="open")
        db.add(pos)
        db.flush()
        record_position_opened(db, pos.id, total_cost, ticker)

        # Log decision
        self._log_decision(db, ticker, "buy", quantity, price, total_cost, reasoning, confidence,
                           portfolio_before, self.get_portfolio(db))

        db.commit()
        return {"success": True, "position_id": pos.id, "ticker": ticker, "quantity": quantity, "cost": total_cost}

    def execute_sell(self, db: Session, position_id: int, price: float, reasoning: str, portfolio_before: dict, confidence: float = 0.7) -> dict:
        """Satis yap."""
        pos = db.query(PortfolioPosition).filter(PortfolioPosition.id == position_id).first()
        if not pos:
            return {"success": False, "error": "Pozisyon bulunamadi"}

        proceeds = round(pos.quantity * price, 2)
        pos.status = "closed"
        pos.exit_price = price
        pos.exit_date = datetime.utcnow()
        record_position_closed(db, pos.id, proceeds, pos.ticker)

        self._log_decision(db, pos.ticker, "sell", pos.quantity, price, proceeds, reasoning, confidence,
                           portfolio_before, self.get_portfolio(db))

        db.commit()
        return {"success": True, "ticker": pos.ticker, "proceeds": proceeds, "pl": round(proceeds - pos.quantity * pos.entry_price, 2)}

    def _log_decision(self, db: Session, ticker: str, action: str, quantity: float, price: float,
                      amount: float, reasoning: str, confidence: float, portfolio_before: dict, portfolio_after: dict):
        """Her karari trading_decisions'a yaz."""
        from app.models.core import Prediction  # noqa
        # Raw SQL daha guvenli
        db.execute(
            db.query(Prediction)._annotations,
        )
        # Manual insert
        import sqlalchemy as sa
        meta = sa.MetaData()
        meta.reflect(bind=db.get_bind())
        td_table = meta.tables["trading_decisions"]
        db.execute(td_table.insert().values(
            ticker=ticker.upper(), action=action, quantity=quantity, price=price,
            total_amount=amount, reasoning=reasoning[:1000],
            factors=json.dumps({}), confidence=confidence,
            portfolio_value_before=portfolio_before.get("total_market_value"),
            portfolio_value_after=portfolio_after.get("total_market_value"),
            created_at=datetime.utcnow(),
        ))
        db.flush()

    # ── Main Decision Loop ──

    async def think_and_act(self, db: Session, exchanges: list[str] | None = None) -> dict:
        """Ana dusunme dongusu: durumu degerlendir → firsat ara → al/sat karari ver."""
        portfolio = self.get_portfolio(db)

        # 1. Piyasayi tara
        from app.services.screener_service import stage1_prescreen, get_universe
        tickers = get_universe(exchanges) if exchanges else get_universe(["NASDAQ", "NYSE"])

        candidates = await stage1_prescreen(tickers)
        actions = []
        total_bought = 0

        # 2. Her adayi degerlendir
        for c in candidates[:10]:  # en iyi 10 aday
            if total_bought >= 3:
                break  # max 3 gunluk alim
            if portfolio["position_count"] >= self.max_positions:
                break

            ticker = c["ticker"]
            price = c["price"]
            score = c["technical_score"]

            if score < 60:
                continue

            # Mevcut pozisyon var mi?
            existing = [p for p in portfolio["positions"] if p["ticker"] == ticker]
            if existing:
                continue

            # Derin analiz
            analysis = self.analyze_single(ticker)
            composite = analysis.get("composite_score", 0)
            sentiment = analysis.get("sentiment_score", 50)
            risk = analysis.get("risk_score", 50)

            if composite < 50:
                continue

            # Karar: AL
            value_at_risk = portfolio["cash"] * self.max_per_position_pct
            max_qty = value_at_risk / price if price > 0 else 0
            buy_qty = round(max_qty * (composite / 100) * 0.8, 2)
            if buy_qty < 1:
                buy_qty = 1  # minimum 1 lot

            reasoning = f"Teknik skor: {score:.0f}, compozit: {composite:.0f}, sentiment: {sentiment:.0f}, risk: {risk:.0f}. Piyasa taramasi sonucu secti."

            result = self.execute_buy(db, ticker, buy_qty, price, reasoning, portfolio,
                                      confidence=composite / 100)
            if result["success"]:
                actions.append({"action": "buy", "ticker": ticker, "quantity": buy_qty, "price": price, "reasoning": reasoning})
                total_bought += 1
                portfolio = self.get_portfolio(db)

        # 3. Mevcut pozisyonlari degerlendir (satis karari)
        for p in portfolio["positions"]:
            analysis = self.analyze_single(p["ticker"])
            composite = analysis.get("composite_score", 50)
            risk = analysis.get("risk_score", 50)
            unrealized_pct = ((p["current_price"] or p["entry_price"]) / p["entry_price"] - 1) * 100

            should_sell = False
            sell_reason = ""

            if composite < 35:
                should_sell = True
                sell_reason = f"Composite skor cok dusuk ({composite:.0f}/100)"
            elif risk > 75:
                should_sell = True
                sell_reason = f"Risk seviyesi cok yuksek ({risk:.0f}/100)"
            elif unrealized_pct > 15:
                should_sell = True
                sell_reason = f"Kar realizasyonu (+%{unrealized_pct:.1f})"
            elif unrealized_pct < -10:
                should_sell = True
                sell_reason = f"Zarar kesme (-%{abs(unrealized_pct):.1f})"

            if should_sell:
                current_px = p["current_price"] or p["entry_price"]
                result = self.execute_sell(db, p["id"], current_px, sell_reason, portfolio)
                if result["success"]:
                    actions.append({"action": "sell", "ticker": p["ticker"], "reasoning": sell_reason})
                    portfolio = self.get_portfolio(db)

        return {"actions": actions, "portfolio": portfolio, "timestamp": datetime.utcnow().isoformat()}

    # ── Scheduler-friendly sync wrapper ──

    def run(self, exchanges: list[str] | None = None) -> dict:
        """Ajanı manuel veya scheduler'dan cagirmak icin sync wrapper."""
        db = SessionLocal()
        try:
            result = asyncio.run(self.think_and_act(db, exchanges))
            return result
        finally:
            db.close()


# ── Log/history API ──

def get_trading_logs(db: Session, ticker: str | None = None, limit: int = 50) -> list[dict]:
    """Trading kararlarinin logunu dondur."""
    if ticker:
        query = db.execute(
            db.query(db.text("SELECT * FROM trading_decisions WHERE ticker = :t ORDER BY created_at DESC LIMIT :l")),
            {"t": ticker.upper(), "l": limit},
        )
    else:
        query = db.execute(
            db.query(db.text("SELECT * FROM trading_decisions ORDER BY created_at DESC LIMIT :l")),
            {"l": limit},
        )
    rows = query.fetchall()
    return [dict(r._mapping) for r in rows]
