"""
Orchestrator — Two-stage pipeline:
  Stage 1: Technical pre-screen (hizli, 100+ hisse taranir)
  Stage 2: Full agent team (derin analiz, secilmis adaylara)
"""
import asyncio
from datetime import datetime

from app.agents.scanner_agent import ScannerAgent
from app.agents.fundamental_agent import FundamentalAgent
from app.agents.sentiment_agent import SentimentAgent
from app.agents.risk_agent import RiskAgent
from app.agents.report_agent import ReportAgent
from app.database import SessionLocal
from app.models import Report, StockPick
from app.config import WATCHLIST
from app.services.screener_service import (
    stage1_prescreen, stage2_deep_analysis, get_universe,
)


class Orchestrator:
    def __init__(self):
        self.scanner = ScannerAgent()
        self.fundamental = FundamentalAgent()
        self.sentiment = SentimentAgent()
        self.risk = RiskAgent()
        self.reporter = ReportAgent()
        self.is_running = False
        self.last_error: str | None = None
        self.mode: str = "legacy"  # "legacy" | "two-stage"
        self.exchanges: list[str] = []

    @property
    def agents(self):
        return [self.scanner, self.fundamental, self.sentiment, self.risk, self.reporter]

    def status_snapshot(self) -> dict:
        return {"running": self.is_running, "agents": [a.as_dict() for a in self.agents], "mode": self.mode}

    async def run_pipeline(self, exchanges: list[str] | None = None) -> int:
        if self.is_running:
            raise RuntimeError("Pipeline zaten calisiyor")

        self.is_running = True
        self.last_error = None
        self.mode = "two-stage" if exchanges else "legacy"
        self.exchanges = exchanges or []

        try:
            if self.mode == "two-stage":
                return await self._run_two_stage(exchanges)
            return await self._run_legacy()
        except Exception as e:
            self.last_error = str(e)
            raise
        finally:
            self.is_running = False

    async def _run_legacy(self) -> int:
        """Eski 28 hisseli pipeline."""
        candidates = await self.scanner.run()
        if not candidates:
            return self._persist({"summary": "Tarama kriterlerini gecen aday bulunamadi.", "candidates_scanned": 0, "picks": []})

        candidates = await self.fundamental.run(candidates)
        candidates = await self.sentiment.run(candidates)
        candidates = await self.risk.run(candidates)
        result = await self.reporter.run(candidates)
        return self._persist(result)

    async def _run_two_stage(self, exchanges: list[str]) -> int:
        """Iki asamali pipeline: on tarama → derin analiz."""
        tickers = get_universe(exchanges)
        total_scanned = len(tickers)

        # Stage 1 — Technical pre-screen
        self.scanner._set(self.scanner.RUNNING, f"{total_scanned} hisse teknik taraniyor...")
        stage1 = await stage1_prescreen(tickers)
        self.scanner._set(self.scanner.DONE, f"Stage 1: {len(stage1)}/{total_scanned} hisse secti")

        if not stage1:
            return self._persist({"summary": "Stage 1: teknik taramayi gecen aday bulunamadi.",
                                   "candidates_scanned": total_scanned, "picks": []})

        # Stage 2 — Deep analysis
        self.fundamental._set(self.fundamental.RUNNING, f"Stage 2: {len(stage1)} hisse derin analize giriyor")
        stage2 = await stage2_deep_analysis(stage1)
        self.fundamental._set(self.fundamental.DONE if stage2 else self.fundamental.ERROR, f"Derin analiz: {len(stage2)}")

        if not stage2:
            return self._persist({"summary": "Stage 2: derin analiz tamamlanamadi.",
                                   "candidates_scanned": total_scanned, "picks": []})

        # Score & report
        result = await self.reporter.run(stage2)
        result["candidates_scanned"] = total_scanned  # Stage 1 count
        return self._persist(result)

    def _persist(self, result: dict) -> int:
        db = SessionLocal()
        try:
            report = Report(created_at=datetime.utcnow(), summary=result["summary"],
                            candidates_scanned=result["candidates_scanned"])
            db.add(report)
            db.flush()
            for pick in result["picks"]:
                db.add(StockPick(report_id=report.id, ticker=pick["ticker"],
                    price=pick["price"], momentum_pct=pick["momentum_pct"],
                    fundamental_score=pick["fundamental_score"],
                    sentiment_score=pick["sentiment_score"],
                    risk_score=pick["risk_score"],
                    composite_score=pick["composite_score"],
                    pe_ratio=pick.get("pe_ratio"),
                    volatility_annualized=pick.get("volatility_annualized"),
                    max_drawdown_pct=pick.get("max_drawdown_pct"),
                    narrative=pick["narrative"]))
            db.commit()
            return report.id
        finally:
            db.close()


orchestrator = Orchestrator()
