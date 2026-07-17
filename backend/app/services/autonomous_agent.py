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
import logging
from datetime import datetime
from app.config import now_istanbul, market_is_open
from typing import Optional

import yfinance as yf
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

from app.database import SessionLocal
from app.models.core import PortfolioPosition, TradingDecision, PendingOrder
from app.models.balance import BalanceTransaction
from app.models.portfolio import Portfolio
from app.services.balance_service import (
    get_balance, deposit, record_position_opened, record_position_closed,
    ensure_portfolio,
)
from app.services.market_data import get_live_prices
from app.services.memory_service import store_research_memory


# ── Agent Brain ──

class AutonomousAgent:
    """Tamamen otonom trading ajani. LLM karar verir, DB'ye loglar.

    Çoklu portföy: portfolio_slug ile belirli portföyü yönetir.
    """

    def __init__(self, portfolio_slug: str = "bist", model: str = "ensemble-light"):
        self.model = model
        self.portfolio_slug = portfolio_slug
        # Portfolio kaydını DB'de guarantee et — slug geçersizse ValueError
        from app.config import PORTFOLIOS
        cfg = PORTFOLIOS.get(portfolio_slug)
        if cfg is None:
            raise ValueError(f"Bilinmeyen portföy slug: {portfolio_slug}")
        self.portfolio_display_name = cfg["display_name"]
        self.portfolio_exchanges = cfg.get("exchanges", [])
        self.max_positions = cfg.get("max_positions", 8)
        self.max_per_position_pct = cfg.get("max_per_position_pct", 0.25)
        self.min_confidence = 0.6
        # portfolio_id lazy — run() sırasında ensure_portfolio ile set edilir
        self._portfolio_id: Optional[int] = None

    def _ensure_portfolio_id(self, db: Session) -> int:
        """Portfolio.id'yi DB'den al (ilk çağrıda)."""
        if self._portfolio_id is None:
            p = ensure_portfolio(db, self.portfolio_slug)
            self._portfolio_id = p.id
        return self._portfolio_id

    @property
    def name(self) -> str:
        return f"autonomous_agent_{self.portfolio_slug}"

    # ── Tools ──

    async def get_market_status(self, exchanges: list[str] | None = None) -> dict:
        """Piyasa durumu: tum evrenden hizli teknik tarama."""
        from app.services.screener_service import stage1_prescreen, get_universe
        tickers = get_universe(exchanges)
        return await stage1_prescreen(tickers)

    async def analyze_single(self, ticker: str) -> dict:
        """Tek hisse detayli analiz (full agent pipeline)."""
        from app.services.yf_utils import safe_ticker_info, safe_ticker_history
        info = safe_ticker_info(ticker)
        hist = safe_ticker_history(ticker, period="3mo")
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
        from app.agents.fundamental_agent import FundamentalAgent
        from app.agents.sentiment_agent import SentimentAgent
        from app.agents.risk_agent import RiskAgent
        from app.agents.report_agent import ReportAgent

        f = FundamentalAgent(); s = SentimentAgent(); r = RiskAgent(); rep = ReportAgent()
        c = await f.run([candidate])
        c = await s.run(c)
        c = await r.run(c)
        return c[0] if c else candidate

    def get_portfolio(self, db: Session) -> dict:
        """Mevcut portfoy ve bakiye durumu — sadece bu portföyün pozisyonları."""
        portfolio_id = self._ensure_portfolio_id(db)
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        cash = portfolio.cash if portfolio else 0.0
        positions = (
            db.query(PortfolioPosition)
            .filter(PortfolioPosition.status == "open")
            .filter(PortfolioPosition.portfolio_id == portfolio_id)
            .all()
        )
        total_cost = sum(p.quantity * p.entry_price for p in positions)
        tickers = [p.ticker for p in positions]
        prices = get_live_prices(tickers) if tickers else {}
        total_market = 0
        for p in positions:
            px = prices.get(p.ticker, {}).get("price") or p.entry_price
            total_market += p.quantity * px

        return {
            "portfolio_id": portfolio_id,
            "portfolio_slug": self.portfolio_slug,
            "portfolio_name": self.portfolio_display_name,
            "cash": cash,
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
        portfolio_id = self._ensure_portfolio_id(db)
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if portfolio is None:
            return {"success": False, "error": f"Portföy bulunamadı: {portfolio_id}"}
        total_cost = round(quantity * price, 2)
        if portfolio.cash < total_cost:
            return {"success": False, "error": f"Yetersiz bakiye. Gereken: ${total_cost}, Mevcut: ${portfolio.cash}"}

        pos = PortfolioPosition(
            ticker=ticker.upper(), quantity=quantity, entry_price=price,
            entry_date=now_istanbul(), status="open",
            portfolio_id=portfolio_id,
        )
        db.add(pos)
        db.flush()
        record_position_opened(db, pos.id, total_cost, ticker, portfolio_id=portfolio_id)

        # Log decision
        self._log_decision(db, ticker, "buy", quantity, price, total_cost, reasoning, confidence,
                           portfolio_before, self.get_portfolio(db))

        db.commit()
        return {"success": True, "position_id": pos.id, "ticker": ticker, "quantity": quantity, "cost": total_cost}

    def execute_sell(self, db: Session, position_id: int, price: float, reasoning: str, portfolio_before: dict, confidence: float = 0.7) -> dict:
        """Satis yap."""
        portfolio_id = self._ensure_portfolio_id(db)
        pos = db.query(PortfolioPosition).filter(PortfolioPosition.id == position_id).first()
        if not pos:
            return {"success": False, "error": "Pozisyon bulunamadi"}
        if pos.portfolio_id != portfolio_id:
            return {"success": False, "error": f"Pozisyon bu portföye ait değil (pos.portfolio_id={pos.portfolio_id})"}

        proceeds = round(pos.quantity * price, 2)
        pos.status = "closed"
        pos.exit_price = price
        pos.exit_date = now_istanbul()
        record_position_closed(db, pos.id, proceeds, pos.ticker, portfolio_id=portfolio_id)

        self._log_decision(db, pos.ticker, "sell", pos.quantity, price, proceeds, reasoning, confidence,
                           portfolio_before, self.get_portfolio(db))

        db.commit()
        return {"success": True, "ticker": pos.ticker, "proceeds": proceeds, "pl": round(proceeds - pos.quantity * pos.entry_price, 2)}

    def _log_decision(self, db: Session, ticker: str, action: str, quantity: float, price: float,
                      amount: float, reasoning: str, confidence: float, portfolio_before: dict, portfolio_after: dict):
        """Her karari trading_decisions'a yaz (TradingDecision modeli ile)."""
        portfolio_id = self._ensure_portfolio_id(db)
        db.add(TradingDecision(
            ticker=ticker.upper(), action=action, quantity=quantity, price=price,
            total_amount=amount, reasoning=reasoning[:1000],
            factors=json.dumps({}), confidence=confidence,
            portfolio_value_before=portfolio_before.get("total_market_value"),
            portfolio_value_after=portfolio_after.get("total_market_value"),
            portfolio_id=portfolio_id,
        ))
        db.flush()

    # ── Stuck Position Cleanup ──

    def _cleanup_stuck_positions(self, db: Session, portfolio: dict):
        """Fiyatı tutarlı şekilde gelemeyen (delisted/veya yfinance sorunlu)
        pozisyonları son bilinen entry_price ile kapat. Her turda çalışır."""
        from app.models.core import TradingDecision

        stuck_tickers = [p["ticker"] for p in portfolio["positions"]
                         if p.get("current_price") is None]
        if not stuck_tickers:
            return

        logger.info("Stuck position cleanup: %s", stuck_tickers)
        for pos_data in portfolio["positions"]:
            if pos_data.get("current_price") is not None:
                continue

            ticker = pos_data["ticker"]
            pos_id = pos_data["id"]
            entry_price = pos_data["entry_price"]
            quantity = pos_data.get("quantity", 1)

            # Pozisyonu entry_price ile kapat (breakeven — fiyat alınamadığı için)
            pos = db.query(PortfolioPosition).filter(PortfolioPosition.id == pos_id).first()
            if not pos or pos.status != "open":
                continue

            pos.status = "closed"
            pos.exit_price = entry_price
            pos.exit_date = now_istanbul()
            pos.notes = "Auto-closed: price unavailable (delisted/yfinance error)"
            proceeds = round(quantity * entry_price, 2)
            record_position_closed(db, pos_id, proceeds, ticker)

            self._log_decision(
                db, ticker, "sell", quantity, entry_price, proceeds,
                f"Otomatik kapatma: fiyat alinamiyor (delisted/yfinance hatasi), "
                f"entry_price={entry_price} ile kapatildi",
                confidence=0.5, portfolio_before=portfolio,
                portfolio_after=self.get_portfolio(db),
            )
            logger.info("Closed stuck position: %s x%s @ $%s (breakeven)", ticker, quantity, entry_price)
            db.commit()

    # ── Main Decision Loop (LLM-powered) ──

    async def think_and_act(self, db: Session, exchanges: list[str] | None = None) -> dict:
        """Ana dusunme dongusu:
        1. Bekleyen emirleri kontrol et (piyasa acildiysa gerceklestir)
        2. Takili pozisyonlari temizle
        3. Piyasa aciksa → normal karar + islem
           Piyasa kapaliysa → derin analiz + bekleyen emir olustur
        4. LLM/kural-bazli karar ver + uygula
        """
        if exchanges is None:
            exchanges = self.portfolio_exchanges
        portfolio = self.get_portfolio(db)

        # 0. Piyasa acik mi? Exchange tipini belirle
        is_bist = "BIST" in (exchanges or [])
        exchange_label = "BIST" if is_bist else "US"
        market_open = market_is_open(exchange_label)

        # 1. Bekleyen emirleri gerceklestir (piyasa acildiysa)
        if market_open:
            executed = self._execute_pending_orders(db, portfolio)
            if executed:
                portfolio = self.get_portfolio(db)

        # 2. Takili pozisyonlari kapat
        self._cleanup_stuck_positions(db, portfolio)
        portfolio = self.get_portfolio(db)

        # 3. Adaylari topla
        candidates = await self._gather_candidates(db, exchanges, is_bist)

        if not candidates:
            logger.info("[%s] Hic aday bulunamadi", exchange_label)
            return {"actions": [], "decisions": [], "portfolio": self.get_portfolio(db),
                    "timestamp": now_istanbul().isoformat(), "note": "aday yok",
                    "market_open": market_open, "exchange": exchange_label}

        # 4. Piyasa durumuna gore karar
        if market_open:
            # Piyasa acik → normal karar + islem
            actions, decisions = await self._llm_decide(portfolio, candidates, db)
        else:
            # Piyasa kapali → derin analiz + bekleyen emir
            actions = await self._deep_analyze_and_queue(db, candidates, portfolio, is_bist, exchange_label)

        return {"actions": actions, "decisions": decisions if market_open else [],
                "portfolio": self.get_portfolio(db),
                "timestamp": now_istanbul().isoformat(),
                "market_open": market_open, "exchange": exchange_label}

    async def _gather_candidates(self, db: Session, exchanges: list[str], is_bist: bool) -> list[dict]:
        """Aday hisseleri topla — rapordan veya piyasadan."""
        from app.models.core import Report

        latest = db.query(Report).options(
            joinedload(Report.picks)
        ).order_by(Report.created_at.desc()).first()

        candidates = []
        if latest and latest.picks:
            for p in latest.picks:
                is_bist_ticker = p.ticker.endswith(".IS")
                if is_bist != is_bist_ticker:
                    continue
                candidates.append({
                    "ticker": p.ticker,
                    "price": p.price,
                    "momentum_5d": p.momentum_pct or 0,
                    "rsi_14": p.rsi_14 if p.rsi_14 is not None else 50,
                    "technical_score": p.composite_score or 50,
                    "composite_score": p.composite_score or 50,
                    "fundamental_score": p.fundamental_score or 50,
                    "sentiment_score": p.sentiment_score or 50,
                    "risk_score": p.risk_score or 50,
                    "pe_ratio": p.pe_ratio,
                    "volatility": p.volatility_annualized,
                    "narrative": p.narrative or "",
                    "fair_value": p.fair_value,
                    "margin_pct": p.margin_pct,
                    "llm_reasoning": p.llm_reasoning,
                })
            candidates.sort(key=lambda c: c["composite_score"], reverse=True)
            logger.info("[%s] Rapor pick'leri: %d aday", "BIST" if is_bist else "US", len(candidates))
        else:
            from app.services.screener_service import stage1_prescreen, get_universe
            tickers = get_universe(exchanges) if exchanges else get_universe(["NASDAQ", "NYSE"])
            scanned = await stage1_prescreen(tickers)
            for c in scanned[:8]:
                try:
                    a = await self.analyze_single(c["ticker"])
                    candidates.append({**c,
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

        return candidates

    def _execute_pending_orders(self, db: Session, portfolio: dict) -> int:
        """Bekleyen emirleri gerceklestir (piyasa acildiginda cagrilir)."""
        executed = 0
        pending = (
            db.query(PendingOrder)
            .filter(PendingOrder.status == "pending")
            .filter(PendingOrder.portfolio_id == self._ensure_portfolio_id(db))
            .all()
        )
        for order in pending:
            try:
                # Guncel fiyati al
                prices = get_live_prices([order.ticker])
                current_price = prices.get(order.ticker, {}).get("price")
                if not current_price or current_price <= 0:
                    continue

                if order.action == "buy":
                    result = self.execute_buy(
                        db, order.ticker, order.quantity, current_price,
                        f"Bekleyen emir gerceklesti: {order.reasoning}",
                        portfolio, confidence=order.confidence,
                    )
                else:
                    # sell - pozisyonu bul
                    pos = (
                        db.query(PortfolioPosition)
                        .filter(PortfolioPosition.ticker == order.ticker)
                        .filter(PortfolioPosition.status == "open")
                        .filter(PortfolioPosition.portfolio_id == self._ensure_portfolio_id(db))
                        .first()
                    )
                    if pos:
                        result = self.execute_sell(
                            db, pos.id, current_price,
                            f"Bekleyen emir gerceklesti: {order.reasoning}",
                            portfolio, confidence=order.confidence,
                        )
                    else:
                        result = {"success": False, "error": "Pozisyon bulunamadi"}

                if result.get("success"):
                    order.status = "executed"
                    order.executed_at = now_istanbul()
                    order.price = current_price
                    order.notes = f"Piyasa acilisinda gerceklesti @ {current_price}"
                    executed += 1
                    portfolio = self.get_portfolio(db)
                    logger.info("Pending order executed: %s %s x%s @ %s",
                                order.action, order.ticker, order.quantity, current_price)
                else:
                    order.notes = f"Basarisiz: {result.get('error', 'bilinmeyen')}"
                    order.status = "cancelled"
                    logger.warning("Pending order failed: %s", result.get("error"))
            except Exception as e:
                order.notes = f"Hata: {e}"
                order.status = "cancelled"
                logger.error("Pending order error: %s", e)

        if executed:
            db.commit()
        return executed

    async def _deep_analyze_and_queue(self, db: Session, candidates: list[dict],
                                      portfolio: dict, is_bist: bool, exchange_label: str) -> list[dict]:
        """Piyasa kapaliyken derin analiz + bekleyen emir olustur."""
        from app.skills import stock_analysis as _stock_skill

        actions = []
        cash = portfolio.get("cash", 0)
        max_positions = self.max_positions
        current_count = portfolio.get("position_count", 0)

        # Sadece en guclu 5 adaya derin analiz yap
        deep_candidates = candidates[:5]
        logger.info("[%s] Piyasa KAPALI — %d aday derin analiz ediliyor...", exchange_label, len(deep_candidates))

        for c in deep_candidates:
            if current_count + len(actions) >= max_positions or cash <= 0:
                break

            try:
                # Deep analysis via stock_analysis skill
                analysis = await _stock_skill.run(c["ticker"], db=db)
                conclusion = analysis.get("conclusion", "hold")
                composite = analysis.get("scores", {}).get("composite", c.get("composite_score", 0)) or 0
                momentum = analysis.get("momentum_pct", c.get("momentum_5d", 0)) or 0

                # Sadece buy/strong_buy ve composite >= 60
                if conclusion not in ("buy", "strong_buy") or composite < 60:
                    logger.debug("[%s] %s elendi: conclusion=%s composite=%.0f",
                                 exchange_label, c["ticker"], conclusion, composite)
                    continue

                # Buy emri olustur
                price = c.get("price", 0) or 0
                if price <= 0:
                    continue

                max_per_pos = cash * self.max_per_position_pct
                budget = min(max_per_pos, cash * 0.5)
                qty = max(1, int(budget / price))

                reasoning = (
                    f"Piyasa kapaliyken derin analiz: conclusion={conclusion} composite={composite:.0f} "
                    f"bias={analysis.get('bias_pct', 0)}% F/K={c.get('pe_ratio', 'N/A')} "
                    f"fair_value={analysis.get('fair_value', 'N/A')} "
                    f"margin={analysis.get('margin_pct', 0):.1f}%"
                )
                if analysis.get("llm_reasoning"):
                    reasoning += f" | AI: {analysis['llm_reasoning'][:150]}"

                order = PendingOrder(
                    portfolio_id=self._ensure_portfolio_id(db),
                    ticker=c["ticker"], action="buy", quantity=qty,
                    price=price, reasoning=reasoning[:1000],
                    analysis_json={
                        "conclusion": conclusion,
                        "composite": composite,
                        "bias_pct": analysis.get("bias_pct"),
                        "fundamental": analysis.get("scores", {}).get("fundamental"),
                        "sentiment": analysis.get("scores", {}).get("sentiment"),
                        "risk": analysis.get("scores", {}).get("risk"),
                        "fair_value": analysis.get("fair_value"),
                        "margin_pct": analysis.get("margin_pct"),
                        "llm_reasoning": analysis.get("llm_reasoning"),
                        "llm_target_price": analysis.get("llm_target_price"),
                        "momentum_pct": momentum,
                    },
                    confidence=max(0.65, composite / 100),
                    exchange=exchange_label,
                )
                db.add(order)
                db.flush()
                actions.append({
                    "action": "queue_buy", "ticker": c["ticker"],
                    "quantity": qty, "price": price,
                    "reasoning": f"Bekleyen emir: {conclusion} (composite={composite:.0f})",
                    "order_id": order.id,
                })
                cash -= budget
                logger.info("[%s] Bekleyen emir: BUY %s x%s @ %s (composite=%.0f)",
                            exchange_label, c["ticker"], qty, price, composite)

            except Exception as e:
                logger.warning("[%s] Derin analiz basarisiz %s: %s", exchange_label, c["ticker"], e)

        if actions:
            db.commit()
            logger.info("[%s] %d bekleyen emir olusturuldu", exchange_label, len(actions))
        return actions

    async def _llm_decide(self, portfolio: dict, candidates: list[dict], db: Session) -> tuple:
        """LLM portfoy + adaylari degerlendirip dinamik al/sat kararlari verir.
        
        Falls back to rule-based decisions when no LLM is configured.
        """
        from app.services.llm_bridge import generate, get_default_model
        from app.config import TOP_N_PICKS

        # Try LLM first
        model = get_default_model()
        if model is not None:
            try:
                return await self._llm_decide_with_llm(portfolio, candidates, db)
            except Exception as e:
                logger.warning("LLM karar verme basarisiz, kural-bazli moda geciliyor: %s", e)

        # Fallback: rule-based decisions
        return self._rule_based_decide(portfolio, candidates, db, TOP_N_PICKS)

    def _rule_based_decide(self, portfolio: dict, candidates: list[dict], db: Session, top_n: int = 5) -> tuple:
        """Kural-bazli portfoy kararlari (LLM yokken calisir)."""
        actions = []
        decisions = []

        # Use a simple per-ticker cache to avoid repeated yfinance calls
        _rsi_cache: dict[str, float] = {}

        def _get_rsi(ticker: str, default: float = 50) -> float:
            """RSI'yi bul: once candidate'da ara, yoksa yfinance'dan canli hesapla."""
            # Check cache first
            if ticker in _rsi_cache:
                return _rsi_cache[ticker]

            # Check if candidate already has non-default RSI
            cand = next((c for c in candidates if c["ticker"] == ticker), None)
            if cand and cand.get("rsi_14", 0) != 50:
                _rsi_cache[ticker] = float(cand["rsi_14"])
                return _rsi_cache[ticker]

            # Fetch live RSI from yfinance
            try:
                import yfinance as yf
                import numpy as np
                hist = yf.Ticker(ticker).history(period="1mo")
                if not hist.empty and len(hist) >= 15:
                    closes = hist["Close"].values
                    delta = np.diff(closes)
                    gains = np.where(delta > 0, delta, 0)
                    losses = np.where(delta < 0, -delta, 0)
                    avg_g = float(np.mean(gains[-14:]))
                    avg_l = float(np.mean(losses[-14:]))
                    rsi = 100 - (100 / (1 + avg_g / avg_l)) if avg_l > 0 else 100
                    rsi = round(rsi, 1)
                    _rsi_cache[ticker] = rsi
                    return rsi
            except Exception:
                pass
            return default

        # 1. Check existing positions — sell if overbought (RSI > 75) or stop-loss (< -15%)
        for pos in portfolio.get("positions", []):
            ticker = pos["ticker"]
            rsi = _get_rsi(ticker)
            unrealized = pos.get("unrealized_pl", 0)
            # Sell trigger: RSI aşırı alım veya stop-loss veya rapor skoru düştü
            should_sell = rsi > 75
            if not should_sell:
                candidate = next((c for c in candidates if c["ticker"] == ticker), None)
                if candidate:
                    should_sell = candidate.get("composite_score", 50) < 40
            if not should_sell:
                entry_cost = pos.get("entry_price", 1) * 0.15 * pos.get("quantity", 1)
                should_sell = unrealized < -entry_cost
            if should_sell:
                candidate = next((c for c in candidates if c["ticker"] == ticker), None)
                price = candidate.get("price", 0) if candidate else 0
                pos_id = pos.get("id")
                if price > 0 and pos_id:
                    result = self.execute_sell(db, pos_id, price,
                        f"Kural bazli satis: RSI={rsi:.0f}, PL=${unrealized:.2f}",
                        portfolio, confidence=0.6)
                    if result["success"]:
                        actions.append({"action": "sell", "ticker": ticker, "reasoning": result.get("error", "")})
                        portfolio = self.get_portfolio(db)

        # 2. Buy top candidates if cash available
        cash = portfolio.get("cash", 0)
        max_per_pos = cash * self.max_per_position_pct
        current_count = portfolio.get("position_count", 0)

        # Collect eligible buy candidates first, then allocate budgets
        eligible: list[dict] = []
        for c in candidates[:top_n]:
            if current_count + len(eligible) >= self.max_positions:
                break
            score = c.get("composite_score", c.get("technical_score", 0))
            rsi = _get_rsi(c["ticker"])
            mom = c.get("momentum_5d", 0)
            if score >= 60 and rsi < 65 and mom > -5 and c.get("price", 0) > 0:
                eligible.append({**c, "_score": score, "_rsi": rsi, "_mom": mom})

        budgets: dict[str, float] = {}
        if eligible and cash > 0:
            try:
                # ponytail: mean-variance uses random search not SLSQP; upgrade to scipy.optimize when scipy is a dep
                from app.services.portfolio_optimizer import allocate_buy_budgets
                budgets = allocate_buy_budgets(
                    tickers=[e["ticker"] for e in eligible],
                    prices=[float(e["price"]) for e in eligible],
                    cash=float(cash),
                    returns_matrix=None,
                    max_weight=float(self.max_per_position_pct),
                )
            except Exception:
                budgets = {}

        for c in eligible:
            if current_count >= self.max_positions:
                break
            if cash <= 0:
                break
            price = float(c["price"])
            budget = float(budgets.get(c["ticker"], max_per_pos)) if budgets else max_per_pos
            budget = min(budget, cash, max_per_pos if max_per_pos > 0 else budget)
            qty = max(1, int(budget / price)) if price > 0 and budget > 0 else 0
            if qty > 0 and budget > 0:
                score, rsi, mom = c["_score"], c["_rsi"], c["_mom"]
                result = self.execute_buy(
                    db, c["ticker"], qty, price,
                    f"Kural bazli alis: skor={score:.0f} RSI={rsi:.0f} momentum=%{mom:.1f}",
                    portfolio, confidence=0.6,
                )
                if result["success"]:
                    actions.append({
                        "action": "buy", "ticker": c["ticker"], "quantity": qty, "price": price,
                        "reasoning": f"skor={score:.0f} RSI={rsi:.0f}",
                    })
                    cash -= qty * price
                    current_count += 1
                    portfolio = self.get_portfolio(db)

        return actions, decisions

    async def _llm_decide_with_llm(self, portfolio: dict, candidates: list[dict], db: Session) -> tuple:
        """LLM ile portfoy kararlari.

        stock_analysis skill entegrasyonu: karar öncesi top adayları analyze_stock
        skill'ile zengin analiz eder (bias rule Python ile uygulanır), sonuç prompt'a
        enjekte edilir. LLM zengin analiz görür, mevcut JSON karar formatı korunur.
        """
        from app.services.llm_bridge import generate
        from app.skills import stock_analysis as _stock_skill

        pos_text = "\n".join(
            f"  {p['ticker']} x{p['quantity']} @ ${p['entry_price']:.2f} (su an: ${p.get('current_price', '?')}) "
            f"PL: ${p.get('unrealized_pl', 0):.2f}"
            for p in portfolio["positions"]
        ) if portfolio["positions"] else "  (bos portfoy)"

        cand_text = "\n".join(
            f"  {c['ticker']} ${c['price']:.2f} | "
            f"teknik:{c['technical_score']:.0f} compozit:{c['composite_score']:.0f} "
            f"temel:{c['fundamental_score']:.0f} sentiment:{c['sentiment_score']:.0f} risk:{c['risk_score']:.0f} "
            f"RSI:{c['rsi_14']:.0f} mom:%{c['momentum_5d']:.1f}"
            + (f" F/K:{c['pe_ratio']:.1f}" if c.get("pe_ratio") else "")
            + f" | {c.get('narrative', '')[:80]}"
            for c in candidates
        )

        # --- stock_analysis skill zenginleştirme (behavior rules uygulandı) ---
        enhanced_analyses: list[dict] = []
        for c in candidates[:3]:  # en güçlü 3 aday
            try:
                result = await _stock_skill.run(c["ticker"], db=db)
                enhanced_analyses.append({
                    "ticker": result["ticker"],
                    "conclusion": result["conclusion"],
                    "bias_pct": result["bias_pct"],
                    "data_missing": result["data_missing"],
                })
            except Exception as e:
                logger.warning("skill analyze_stock %s başarısız: %s", c.get("ticker"), e)

        enhanced_text = "\n".join(
            f"  {a['ticker']}: {a['conclusion']} (bias: {a.get('bias_pct', 'veri yok')}%)"
            + (f" [eksik veri: {', '.join(a['data_missing'])}]" if a["data_missing"] else "")
            for a in enhanced_analyses
        ) if enhanced_analyses else "  (skill analizi başarısız — tarama verisiyle devam)"

        prompt = f"""Sen ORBIS FINAI'nin otonom portfoy yoneticisisin. $10,000 sanal bakiye ile gercek piyasa kosullarinda islem yapiyorsun.
Amacin: riski yonetererek maksimum getiri saglamak.

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

=== SKILL ZENGIN ANALIZ (bias rule Python ile uygulandi) ===
{enhanced_text}
Not: "hold" conclusion'lı adaylar bias>5% nedeniyle buy engellenmiş olabilir.

=== GOREV ===
Asagidaki JSON formatinda al/sat/elde_tut kararlarini ver. Kararlarini verirken:
- Risk yonetimi: tek hisseye max %25, en az 3 farkli sektor
- Kar realizasyonu: asiri yukselenleri sat
- Zarar kesme: düsen pozisyonlari degerlendir
- Firsat degerlendirme: guclu adaylari ekle (SKILL conclusion'ına dikkat et)
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

        response = await generate(prompt=prompt,
            system="Sen deneyimli bir portfoy yoneticisisin. Risk yonetimi, sektor cesitlendirmesi ve piyasa zamanlamasi konularinda uzmansin. Skill analiz conclusion'larina saygi goster.",
            temperature=0.4, max_tokens=1024)

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
                    result = self.execute_buy(db, ticker, qty, price, reasoning, portfolio_before, confidence=0.75)
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

    # ── Scheduler-friendly sync wrapper ──

    def run(self, exchanges: list[str] | None = None) -> dict:
        """Ajanı manuel veya scheduler'dan cagirmak icin sync wrapper.

        exchanges None ise PORTFOLIOS[slug]["exchanges"] kullanılır.
        """
        if exchanges is None:
            exchanges = self.portfolio_exchanges
        db = SessionLocal()
        try:
            return asyncio.run(self.think_and_act(db, exchanges))
        finally:
            db.close()


# ── Log/history API ──

def get_trading_logs(db: Session, ticker: str | None = None, limit: int = 50, portfolio_id: int | None = None) -> list[dict]:
    """Trading kararlarinin logunu dondur. portfolio_id verilirse sadece o portföyün."""
    from app.models.core import TradingDecision
    q = db.query(TradingDecision)
    if ticker:
        q = q.filter(TradingDecision.ticker == ticker.upper())
    if portfolio_id is not None:
        q = q.filter(TradingDecision.portfolio_id == portfolio_id)
    q = q.order_by(TradingDecision.created_at.desc()).limit(limit)
    return [
        {
            "id": r.id, "ticker": r.ticker, "action": r.action,
            "quantity": r.quantity, "price": r.price, "total_amount": r.total_amount,
            "reasoning": r.reasoning, "confidence": r.confidence,
            "portfolio_id": r.portfolio_id,
            "portfolio_value_before": r.portfolio_value_before,
            "portfolio_value_after": r.portfolio_value_after,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in q.all()
    ]
