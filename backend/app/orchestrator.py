"""
Orchestrator
Beş ajanı (Tarama -> Temel Analiz -> Haber/Sentiment -> Risk -> Rapor) sırayla
çalıştırır. Temel Analiz, Sentiment ve Risk teorik olarak paralel çalışabilir
(hepsi Tarama çıktısına bağımlı, birbirine değil) - burada asyncio.gather ile
gerçekten paralel koşturuyoruz.
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


class Orchestrator:
    def __init__(self):
        self.scanner = ScannerAgent()
        self.fundamental = FundamentalAgent()
        self.sentiment = SentimentAgent()
        self.risk = RiskAgent()
        self.reporter = ReportAgent()
        self.is_running = False
        self.last_error: str | None = None

    @property
    def agents(self):
        return [self.scanner, self.fundamental, self.sentiment, self.risk, self.reporter]

    def status_snapshot(self) -> dict:
        return {
            "running": self.is_running,
            "agents": [a.as_dict() for a in self.agents],
        }

    async def run_pipeline(self) -> int:
        """Pipeline'ı çalıştırır ve oluşan Report kaydının id'sini döner."""
        if self.is_running:
            raise RuntimeError("Pipeline zaten çalışıyor")

        self.is_running = True
        self.last_error = None
        try:
            candidates = await self.scanner.run()

            if not candidates:
                report_id = self._persist({"summary": "Tarama kriterlerini geçen aday bulunamadı.",
                                            "candidates_scanned": 0, "picks": []})
                return report_id

            # Temel analiz, sentiment ve risk aynı aday listesi üzerinde bağımsız
            # çalışabilir; ancak risk agent 'history' alanını tükettiği için
            # sırayı koruyoruz (fundamental/sentiment history'e dokunmaz).
            candidates = await self.fundamental.run(candidates)
            candidates = await self.sentiment.run(candidates)
            candidates = await self.risk.run(candidates)

            result = await self.reporter.run(candidates)
            report_id = self._persist(result)
            return report_id
        except Exception as e:
            self.last_error = str(e)
            raise
        finally:
            self.is_running = False

    def _persist(self, result: dict) -> int:
        db = SessionLocal()
        try:
            report = Report(
                created_at=datetime.utcnow(),
                summary=result["summary"],
                candidates_scanned=result["candidates_scanned"],
            )
            db.add(report)
            db.flush()

            for pick in result["picks"]:
                db.add(StockPick(
                    report_id=report.id,
                    ticker=pick["ticker"],
                    price=pick["price"],
                    momentum_pct=pick["momentum_pct"],
                    fundamental_score=pick["fundamental_score"],
                    sentiment_score=pick["sentiment_score"],
                    risk_score=pick["risk_score"],
                    composite_score=pick["composite_score"],
                    pe_ratio=pick.get("pe_ratio"),
                    volatility_annualized=pick.get("volatility_annualized"),
                    max_drawdown_pct=pick.get("max_drawdown_pct"),
                    narrative=pick["narrative"],
                ))

            db.commit()
            return report.id
        finally:
            db.close()


orchestrator = Orchestrator()
