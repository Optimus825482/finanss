import asyncio
import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.database import SessionLocal
from app.orchestrator import orchestrator

import yfinance as yf

router = APIRouter(prefix="/api/screener", tags=["screener_analyze"])

logger = logging.getLogger(__name__)


@router.post("/{ticker}/analyze")
async def trigger_deep_analysis(ticker: str, background_tasks: BackgroundTasks):
    """Agent Team pipeline ile detayli analiz baslat."""
    ticker_str = ticker.strip().upper()

    if orchestrator.is_running:
        raise HTTPException(status_code=409, detail="Pipeline zaten calisiyor")

    async def _deep_analysis():
        from datetime import datetime
        from app.services.memory_service import store_research_memory
        app_models = __import__("app.models", fromlist=["Report", "StockPick"])
        Report = app_models.Report
        StockPick = app_models.StockPick
        from app.models.core import Notification
        from app.services.factor_extractor import extract_and_store_factors
        from app.agents.fundamental_agent import FundamentalAgent
        from app.agents.sentiment_agent import SentimentAgent
        from app.agents.risk_agent import RiskAgent
        from app.agents.report_agent import ReportAgent

        try:
            fundamental = FundamentalAgent()
            sentiment = SentimentAgent()
            risk = RiskAgent()
            reporter = ReportAgent()

            # Tek hisse analizi: on taramayi atla, dogrudan yfinance
            t = yf.Ticker(ticker_str)
            info = await asyncio.to_thread(lambda: t.info or {})
            hist = await asyncio.to_thread(lambda: t.history(period="3mo"))
            hist.index = hist.index.tz_localize(None)
            price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
            prev_close = info.get("regularMarketPreviousClose", price)
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
            candidates = [{
                "ticker": ticker_str, "price": price,
                "momentum_pct": round(change_pct, 2),
                "volume_ratio": 1.0, "history": hist,
            }]

            candidates = await fundamental.run(candidates)
            candidates = await sentiment.run(candidates)
            candidates = await risk.run(candidates)
            result = await reporter.run(candidates)

            # DB'ye Report olarak kaydet (BG task → SessionLocal dogrudan, DI calismaz)
            db = SessionLocal()
            try:
                report = Report(
                    created_at=datetime.utcnow(),
                    summary=result.get("summary", ""),
                    candidates_scanned=len(candidates),
                )
                db.add(report)
                db.flush()

                for pick in result.get("picks", []):
                    db.add(StockPick(
                        report_id=report.id, ticker=pick["ticker"],
                        price=pick["price"], momentum_pct=pick["momentum_pct"],
                        fundamental_score=pick["fundamental_score"],
                        sentiment_score=pick["sentiment_score"],
                        risk_score=pick["risk_score"],
                        composite_score=pick["composite_score"],
                        pe_ratio=pick.get("pe_ratio"),
                        volatility_annualized=pick.get("volatility_annualized"),
                        max_drawdown_pct=pick.get("max_drawdown_pct"),
                        narrative=pick.get("narrative", ""),
                    ))

                # Hafizaya da kaydet
                if result.get("picks"):
                    pick = result["picks"][0]
                    await store_research_memory(
                        db=db, ticker=ticker_str, topic="deep_analysis",
                        summary=result.get("summary", ""),
                        source_report_id=report.id,
                        data_snapshot={
                            "price": pick["price"],
                            "composite_score": pick["composite_score"],
                            "fundamental_score": pick["fundamental_score"],
                            "sentiment_score": pick["sentiment_score"],
                            "risk_score": pick["risk_score"],
                            "pe_ratio": pick.get("pe_ratio"),
                            "volatility_annualized": pick.get("volatility_annualized"),
                        },
                        confidence=0.7, ttl_days=30,
                    )

                # Notification
                pick_tickers = [p["ticker"] for p in result.get("picks", [])]
                db.add(Notification(
                    type="report", title="Analiz Tamamlandi",
                    message=f"{ticker_str} detayli analizi hazir. {len(pick_tickers)} hisse onerisi olusturuldu.",
                    report_id=report.id,
                ))

                # RD-Agent: faktor cikar ve memory'e kaydet
                extract_and_store_factors(
                    ticker=ticker_str, candidates=result.get("picks", []),
                    summary=result.get("summary", ""), source_report_id=report.id,
                )

                db.commit()
                logger.info("Deep analysis completed for %s (report #%d)", ticker_str, report.id)
            except Exception as e:
                db.rollback()
                logger.error("DB persist failed for %s deep analysis: %s", ticker_str, e)
                raise
            finally:
                db.close()

        except Exception as e:
            logger.error("Deep analysis failed for %s: %s", ticker_str, e)

    background_tasks.add_task(_deep_analysis)
    return {
        "ticker": ticker_str,
        "started": True,
        "message": f"{ticker_str} icin detayli analiz baslatildi. Agent team calisiyor.",
    }
