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

    # ── Main Decision Loop (LLM-powered) ──

    async def think_and_act(self, db: Session, exchanges: list[str] | None = None) -> dict:
        """Ana dusunme dongusu: piyasayi tara → LLM'e goster → LLM karar versin → uygula."""
        portfolio = self.get_portfolio(db)

        # 1. Piyasayi tara — top candidates
        from app.services.screener_service import stage1_prescreen, get_universe
        tickers = get_universe(exchanges) if exchanges else get_universe(["NASDAQ", "NYSE"])
        candidates = await stage1_prescreen(tickers)
        top = candidates[:8]

        # 2. Top candidates'i derinlemesine analiz et
        analyzed = []
        for c in top:
            try:
                a = self.analyze_single(c["ticker"])
                analyzed.append({
                    "ticker": c["ticker"], "price": c["price"],
                    "technical_score": c["technical_score"],
                    "momentum_5d": c.get("momentum_5d", 0),
                    "rsi_14": c.get("rsi_14", 50),
                    "composite_score": a.get("composite_score", 0),
                    "fundamental_score": a.get("fundamental_score", 50),
                    "sentiment_score": a.get("sentiment_score", 50),
                    "risk_score": a.get("risk_score", 50),
                    "pe_ratio": a.get("pe_ratio"),
                    "volatility": a.get("volatility_annualized"),
                    "narrative": a.get("narrative", ""),
                })
            except Exception:
                pass

        # 3. LLM karar versin
        actions, decisions = await self._llm_decide(portfolio, analyzed, db)
        return {"actions": actions, "decisions": decisions, "portfolio": self.get_portfolio(db),
                "timestamp": datetime.utcnow().isoformat()}

    async def _llm_decide(self, portfolio: dict, candidates: list[dict], db: Session) -> tuple:
        """LLM portfoy + adaylari degerlendirip dinamik al/sat kararlari verir."""
        from app.services.llm_bridge import generate, get_default_model

        # Portfoy ozeti
        pos_text = "\n".join(
            f"  {p['ticker']} x{p['quantity']} @ ${p['entry_price']:.2f} (su an: ${p.get('current_price', '?')}) "
            f"PL: ${p.get('unrealized_pl', 0):.2f}"
            for p in portfolio["positions"]
        ) if portfolio["positions"] else "  (bos portfoy)"

        # Aday ozeti
        cand_text = "\n".join(
            f"  {c['ticker']} ${c['price']:.2f} | "
            f"teknik:{c['technical_score']:.0f} compozit:{c['composite_score']:.0f} "
            f"temel:{c['fundamental_score']:.0f} sentiment:{c['sentiment_score']:.0f} risk:{c['risk_score']:.0f} "
            f"RSI:{c['rsi_14']:.0f} mom:%{c['momentum_5d']:.1f}"
            + (f" F/K:{c['pe_ratio']:.1f}" if c.get("pe_ratio") else "")
            + f" | {c.get('narrative', '')[:80]}"
            for c in candidates
        )

        prompt = f"""Sen ORBIS FINAI'nin otonom portfoy yoneticisisin. $10,000 sanal bakiye ile gercek piyasa kosullarinda islem yapiyorsun.
Amacin: riski yoneterek maksimum getiri saglamak.

=== PORTFOY DURUMU ===
Nakit: ${portfolio['cash']:.2f}
Pozisyon sayisi: {portfolio['position_count']}
Toplam maliyet: ${portfolio['total_cost']:.2f}
Piyasa degeri: ${portfolio['total_market_value']:.2f}
Toplam P/L: ${portfolio['total_pl']:.2f} (%{portfolio['total_pl_pct']:.1f})

Mevcut pozisyonlar:
{pos_text}

=== YATIRIM ADAYLARI (piyasa taramasindan) ===
{cand_text}

=== GOREV ===
Asagidaki JSON formatinda al/sat/elde_tut kararlarini ver. Kararlarini verirken:
- Risk yonetimi: tek hisseye max %25, en az 3 farkli sektor
- Kar realizasyonu: asiri yukselenleri sat
- Zarar kesme: düsen pozisyonlari degerlendir
- Firsat degerlendirme: guclu adaylari ekle
- Portfoy dengesi: nakit/tahvil benzeri guvenli orani koru
- Piyasa kosullari: volatilite ve sentiment'e gore temkinli/agresif ol

JSON format (sadece JSON, aciklama yok):
{{
  "market_assessment": "kisa piyasa degerlendirmesi (1 cumle Turkce)",
  "actions": [
    {{"ticker": "AAPL", "action": "buy", "quantity": 10, "reasoning": "neden aldigini acikla"}},
    {{"ticker": "MSFT", "action": "sell", "position_id": 123, "reasoning": "neden sattigini acikla"}}
  ],
  "portfolio_strategy": "portfoy stratejisi (1 cumle Turkce)"
}}"""

        try:
            model = get_default_model()
            response = await generate(prompt=prompt, system="Sen deneyimli bir portfoy yoneticisisin. Risk yonetimi, sektor cesitlendirmesi ve piyasa zamanlamasi konularinda uzmansin.", temperature=0.4, max_tokens=1024)

            # Parse JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                return [], []

            decision = json.loads(json_match.group(0))
            actions = []
            llm_actions = decision.get("actions", [])

            for act in llm_actions:
                ticker = act["ticker"].upper()
                action_type = act["action"]
                reasoning = act.get("reasoning", "LLM karari")
                portfolio_before = portfolio

                if action_type == "buy":
                    qty = float(act.get("quantity", 1))
                    price = float(next((c["price"] for c in candidates if c["ticker"] == ticker), 0))
                    if price > 0:
                        result = self.execute_buy(db, ticker, qty, price, reasoning, portfolio_before,
                                                  confidence=0.75)
                        if result["success"]:
                            actions.append({"action": "buy", "ticker": ticker, "quantity": qty, "price": price, "reasoning": reasoning})
                            portfolio = self.get_portfolio(db)

                elif action_type == "sell":
                    pos_id = act.get("position_id")
                    if pos_id:
                        price = float(act.get("price", 0))
                        if price <= 0:
                            pos = db.query(PortfolioPosition).filter(PortfolioPosition.id == pos_id).first()
                            prices = get_live_prices([pos.ticker]) if pos else {}
                            price = prices.get(pos.ticker, {}).get("price") or 0
                        result = self.execute_sell(db, pos_id, price, reasoning, portfolio_before, confidence=0.75)
                        if result["success"]:
                            actions.append({"action": "sell", "ticker": ticker, "reasoning": reasoning})
                            portfolio = self.get_portfolio(db)

            return actions, llm_actions
        except Exception as e:
            return [], [{"error": str(e)}]

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
