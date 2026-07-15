"""
Orchestrator — Two-stage pipeline:
  Stage 1: Technical pre-screen (hizli, 100+ hisse taranir)
  Stage 2: Full agent team (derin analiz, secilmis adaylara)
"""
import logging
from datetime import datetime

from app.agents.scanner_agent import ScannerAgent
from app.agents.base import AgentStatus
from app.agents.fundamental_agent import FundamentalAgent
from app.agents.sentiment_agent import SentimentAgent
from app.agents.risk_agent import RiskAgent
from app.agents.report_agent import ReportAgent
from app.database import SessionLocal
from app.models import Report, StockPick
from app.services.screener_service import (
    stage1_prescreen, stage2_deep_analysis, get_universe,
)

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self):
        self.scanner = ScannerAgent()  # sentinel — Stage 1 ilerleme gostergesi
        self.fundamental = FundamentalAgent()
        self.sentiment = SentimentAgent()
        self.risk = RiskAgent()
        self.reporter = ReportAgent()
        self.is_running = False
        self.last_error: str | None = None
        self.progress_log: list[str] = []  # canli log mesajlari

    @property
    def agents(self):
        return [self.scanner, self.fundamental, self.sentiment, self.risk, self.reporter]

    def status_snapshot(self) -> dict:
        return {
            "running": self.is_running,
            "agents": [a.as_dict() for a in self.agents],
            "mode": "two-stage",
            "progress": self.progress_log[-20:] if self.progress_log else [],
            "last_error": self.last_error,
        }

    def _log(self, msg: str):
        self.progress_log.append(msg)
        logger.info("[pipeline] %s", msg)

    async def run_pipeline(self, exchanges: list[str] | None = None) -> int:
        if self.is_running:
            raise RuntimeError("Pipeline zaten calisiyor")

        self.is_running = True
        self.last_error = None
        self.progress_log = []
        self.exchanges = exchanges or []

        try:
            return await self._run_two_stage(exchanges)
        except Exception as e:
            self.last_error = str(e)
            raise
        finally:
            self.is_running = False

    async def _run_two_stage(self, exchanges: list[str] | None) -> int:
        """Iki asamali pipeline: on tarama → derin analiz."""
        tickers = get_universe(exchanges)
        total_scanned = len(tickers)
        self._log(f"Pipeline basladi: {total_scanned} hisse, islem: {exchanges or 'tum evren'}")

        # Stage 1 — Technical pre-screen
        self.scanner._set(AgentStatus.RUNNING, f"{total_scanned} hisse taranacak...")
        self._log(f"Stage 1 basliyor: {total_scanned} hisse taranacak...")
        stage1 = await stage1_prescreen(tickers)
        self._log(f"Stage 1 sonuc: {len(stage1)}/{total_scanned} aday secti")
        self.scanner._set(AgentStatus.DONE, f"Stage 1: {len(stage1)}/{total_scanned} hisse secti")

        if not stage1:
            self._log("Stage 1: aday bulunamadi, rapor kaydedilmiyor")
            return self._persist({"summary": "Stage 1: teknik taramayi gecen aday bulunamadi.",
                                   "candidates_scanned": total_scanned, "picks": []})

        # Stage 2 — Deep analysis
        self.fundamental._set(AgentStatus.RUNNING, f"Stage 2: {len(stage1)} hisse derin analize giriyor")
        self._log(f"Stage 2 basliyor: {len(stage1)} hisse derin analiz...")
        stage2 = await stage2_deep_analysis(stage1)
        self._log(f"Stage 2 sonuc: {len(stage2)} hisse analiz edildi")
        self.fundamental._set(AgentStatus.DONE if stage2 else AgentStatus.ERROR,
                              f"Derin analiz: {len(stage2)}")

        if not stage2:
            self._log("Stage 2: derin analiz tamamlanamadi, rapor kaydedilmiyor")
            return self._persist({"summary": "Stage 2: derin analiz tamamlanamadi.",
                                   "candidates_scanned": total_scanned, "picks": []})

        # Reporter
        self._log(f"Rapor hazirlaniyor: {len(stage2)} pick...")
        result = await self.reporter.run(stage2)
        result["candidates_scanned"] = total_scanned
        pick_count = len(result.get("picks", []))
        self._log(f"Rapor olusturuldu: {pick_count} pick kaydediliyor")
        rid = self._persist(result)
        self._log(f"Rapor #{rid} kaydedildi ({pick_count} pick)")
        return rid

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
