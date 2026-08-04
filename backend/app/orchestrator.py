"""
Orchestrator — Two-stage pipeline:
  Stage 1: Technical pre-screen (hizli, 100+ hisse taranir)
  Stage 2: Full agent team (derin analiz, secilmis adaylara)
"""
import logging
import threading
from datetime import datetime
from app.config import now_istanbul

from app.agents.scanner_agent import ScannerAgent
from app.agents.base import AgentStatus
from app.agents.fundamental_agent import FundamentalAgent
from app.agents.sentiment_agent import SentimentAgent
from app.agents.risk_agent import RiskAgent
from app.agents.report_agent import ReportAgent
from app.database import SessionLocal
from app.models import Report, StockPick, PipelineRun
from app.services.screener_service import (
    stage1_prescreen, stage2_deep_analysis, get_universe,
)
from app.utils.sanitize import sanitize_dict, sanitize_float

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self):
        self.scanner = ScannerAgent()  # sentinel — Stage 1 ilerleme gostergesi
        self.fundamental = FundamentalAgent()
        self.sentiment = SentimentAgent()
        self.risk = RiskAgent()
        self.reporter = ReportAgent()
        self.is_running = False
        self._run_lock = threading.Lock()  # is_running çakışmasına karşı (thread-safe)
        self.last_error: str | None = None
        self.progress_log: list[str] = []  # canli log mesajlari

    @property
    def agents(self):
        return [self.scanner, self.fundamental, self.sentiment, self.risk, self.reporter]

    def status_snapshot(self) -> dict:
        latest_run = None
        try:
            db = SessionLocal()
            latest_run = db.query(PipelineRun).order_by(PipelineRun.started_at.desc()).first()
            db.close()
        except Exception:
            pass
        return {
            "running": self.is_running,
            "agents": [a.as_dict() for a in self.agents],
            "mode": "two-stage",
            "progress": self.progress_log[-20:] if self.progress_log else [],
            "last_error": self.last_error,
            "latest_run_id": latest_run.id if latest_run else None,
            "latest_run_status": latest_run.status if latest_run else None,
        }

    def _begin_persistent_run(self, kind: str, exchanges: list[str] | None) -> str | None:
        try:
            import uuid
            db = SessionLocal()
            run_id = uuid.uuid4().hex
            db.add(PipelineRun(id=run_id, kind=kind, exchange=','.join(exchanges or []), status="running", progress=[]))
            db.commit(); db.close()
            return run_id
        except Exception as e:
            logger.warning("Pipeline run kaydi baslatilamadi: %s", e)
            return None

    def _finish_persistent_run(self, run_id: str | None, status: str, report_id: int | None = None, error: str | None = None):
        if not run_id:
            return
        try:
            db = SessionLocal()
            run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if run:
                run.status = status; run.report_id = report_id; run.error = error
                run.finished_at = now_istanbul(); run.progress = self.progress_log[-50:]
                db.commit()
            db.close()
        except Exception as e:
            logger.warning("Pipeline run kaydi tamamlanamadi: %s", e)

    def _log(self, msg: str):
        self.progress_log.append(msg)
        logger.info("[pipeline] %s", msg)

    async def run_pipeline(self, exchanges: list[str] | None = None) -> int:
        # is_running yarışı: scheduler thread'i + router aynı anda girebilir.
        # Lock almadan çift başlatmayı önle.
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("Pipeline zaten calisiyor")
        try:
            if self.is_running:
                raise RuntimeError("Pipeline zaten calisiyor")
            self.is_running = True
            self.last_error = None
            self.progress_log = []
            run_id = self._begin_persistent_run("standard", exchanges)
            try:
                result = await self._run_two_stage(exchanges)
                self._finish_persistent_run(run_id, "done", report_id=result)
                return result
            except Exception as e:
                self.last_error = str(e)
                self._finish_persistent_run(run_id, "error", error=str(e))
                raise
            finally:
                self.is_running = False
        finally:
            self._run_lock.release()

    async def run_deep_pipeline(self, exchanges: list[str] | None = None) -> int:
        """Deep Batch modu: Stage 2 sonrası her pick için Fair Value + Prediction + LLM."""
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("Pipeline zaten calisiyor")
        try:
            if self.is_running:
                raise RuntimeError("Pipeline zaten calisiyor")
            self.is_running = True
            self.last_error = None
            self.progress_log = []
            run_id = self._begin_persistent_run("deep", exchanges)
            try:
                result = await self._run_deep(exchanges)
                self._finish_persistent_run(run_id, "done", report_id=result)
                return result
            except Exception as e:
                self.last_error = str(e)
                self._finish_persistent_run(run_id, "error", error=str(e))
                raise
            finally:
                self.is_running = False
        finally:
            self._run_lock.release()

    async def _run_two_stage(self, exchanges: list[str] | None) -> int:
        """Iki asamali pipeline: on tarama → derin analiz."""
        # Reset all agents to IDLE at start
        for a in self.agents:
            a._set(AgentStatus.IDLE)

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

        # Stage 2 — Deep analysis (wire orchestrator agent instances for status)
        self.fundamental._set(AgentStatus.RUNNING, f"Stage 2: {len(stage1)} hisse derin analize giriyor")
        self.sentiment._set(AgentStatus.RUNNING, f"Stage 2: sentiment hazir")
        self.risk._set(AgentStatus.RUNNING, f"Stage 2: risk hazir")
        self._log(f"Stage 2 basliyor: {len(stage1)} hisse derin analiz...")
        stage2 = await stage2_deep_analysis(
            stage1,
            fundamental=self.fundamental,
            sentiment=self.sentiment,
            risk=self.risk,
        )
        self._log(f"Stage 2 sonuc: {len(stage2)} hisse analiz edildi")
        done_or_err = AgentStatus.DONE if stage2 else AgentStatus.ERROR
        self.fundamental._set(done_or_err, f"Derin analiz: {len(stage2)}")
        self.sentiment._set(done_or_err, f"Sentiment: {len(stage2)}")
        self.risk._set(done_or_err, f"Risk: {len(stage2)}")

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
        try:
            from app.services.webhook_notify import notify_webhook
            notify_webhook(
                f"ORBIS rapor #{rid}",
                f"{pick_count} pick kaydedildi ({total_scanned} tarandi)",
                {"report_id": rid, "pick_count": pick_count},
            )
        except Exception:
            pass
        return rid

    async def _run_deep(self, exchanges: list[str] | None) -> int:
        """Deep Batch pipeline: Stage 2 sonrasi her pick'e Fair Value + Prediction + LLM."""
        import asyncio as _asyncio

        for a in self.agents:
            a._set(AgentStatus.IDLE)

        tickers = get_universe(exchanges)
        total_scanned = len(tickers)
        self._log(f"Deep Pipeline basladi: {total_scanned} hisse, islem: {exchanges or 'tum evren'}")

        # Stage 1
        self.scanner._set(AgentStatus.RUNNING, f"{total_scanned} hisse taranacak...")
        stage1 = await stage1_prescreen(tickers)
        self._log(f"Stage 1 sonuc: {len(stage1)}/{total_scanned} aday secti")
        self.scanner._set(AgentStatus.DONE, f"Stage 1: {len(stage1)}/{total_scanned}")

        if not stage1:
            return self._persist({"summary": "Stage 1: aday bulunamadi.", "candidates_scanned": total_scanned, "picks": []})

        # Stage 2
        stage2 = await stage2_deep_analysis(stage1, fundamental=self.fundamental, sentiment=self.sentiment, risk=self.risk)
        self._log(f"Stage 2 sonuc: {len(stage2)} hisse")

        if not stage2:
            return self._persist({"summary": "Stage 2: derin analiz tamamlanamadi.", "candidates_scanned": total_scanned, "picks": []})

        # Deep enrichment: Fair Value + Prediction + MA20 bias + LLM per pick
        self._log(f"Deep enrichment: {len(stage2)} pick isleniyor...")

        # Composite score + narrative
        from app.config import SCORING_WEIGHTS
        w = SCORING_WEIGHTS
        for c in stage2:
            c["composite_score"] = round(c["fundamental_score"] * w["fundamental"] + c["sentiment_score"] * w["sentiment"] + (100 - c["risk_score"]) * w["risk"], 1)

        # Fair Value (concurrent)
        async def _deep_enrich(c: dict) -> dict:
            try:
                from app.services.fair_value import calculate_fair_value
                fv = await _asyncio.to_thread(calculate_fair_value, c["ticker"])
                if fv.get("fair_value"):
                    c["fair_value"] = fv["fair_value"]
                    c["margin_pct"] = fv.get("margin_pct")
                    c["valuation_assessment"] = fv.get("assessment")
            except Exception:
                pass
            return c

        stage2 = await _asyncio.gather(*[_deep_enrich(c) for c in stage2])
        stage2 = [c for c in stage2 if c is not None]

        # MA20 bias
        for c in stage2:
            hist = c.get("history")
            if hist is not None and not hist.empty and "Close" in hist:
                closes = [float(x) for x in hist["Close"].dropna().tolist() if x is not None]
                if len(closes) >= 20:
                    ma20 = sum(closes[-20:]) / 20
                    price_val = c.get("price", closes[-1])
                    bias = (price_val - ma20) / ma20 * 100 if ma20 != 0 else None
                    if bias is not None:
                        c["bias_pct"] = round(bias, 2)

        # Sort by composite
        stage2.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
        top_picks = stage2[:8]

        # LLM enrichment: mükerrer token maliyetini önle (R7.1) — ikinci
        # _llm_enrich_pick gather'i kaldırıldı. NOT: _run_deep reporter'ı
        # (_compose_async) çağırmaz; deep mode LLM istiyorsa bu pipeline'ın
        # reporter.run() üzerinden geçmesi gerekir (tek kaynak: _compose_async step 7).

        # ReportAgent is the single report contract: it produces the final
        # narrative, macro context, fair-value enrichment and pick LLM fields.
        # Persisting directly here previously made deep mode skip that stage.
        result = await self.reporter.run(stage2)
        result["candidates_scanned"] = total_scanned

        rid = self._persist(result)
        self._log(f"Deep Rapor #{rid} kaydedildi ({len(result.get('picks', []))} pick)")
        return rid

    def _persist(self, result: dict) -> int:
        db = SessionLocal()
        try:
            report = Report(created_at=now_istanbul(), summary=result["summary"],
                            candidates_scanned=result["candidates_scanned"])
            db.add(report)
            db.flush()
            for pick in result["picks"]:
                # NaN/Inf guard: any agent can produce bad floats — strip them before DB insert
                pick = sanitize_dict(pick)
                db.add(StockPick(report_id=report.id, ticker=pick["ticker"],
                    price=pick["price"], momentum_pct=sanitize_float(pick["momentum_pct"], 0.0),
                    fundamental_score=sanitize_float(pick["fundamental_score"], 50.0),
                    sentiment_score=sanitize_float(pick["sentiment_score"], 50.0),
                    risk_score=sanitize_float(pick["risk_score"], 50.0),
                    composite_score=sanitize_float(pick["composite_score"], 50.0),
                    pe_ratio=pick.get("pe_ratio"),
                    volatility_annualized=pick.get("volatility_annualized"),
                    max_drawdown_pct=pick.get("max_drawdown_pct"),
                    rsi_14=pick.get("rsi_14"),
                    volume_ratio=pick.get("volume_ratio"),
                    momentum_20d=pick.get("momentum_20d"),
                    technical_score=pick.get("technical_score"),
                    narrative=pick["narrative"],
                    # Faz 1 zenginlestirmeleri
                    fair_value=pick.get("fair_value"),
                    margin_pct=pick.get("margin_pct"),
                    valuation_assessment=pick.get("valuation_assessment"),
                    llm_reasoning=pick.get("llm_reasoning"),
                    llm_target_price=pick.get("llm_target_price"),
                    llm_expected_return_pct=pick.get("llm_expected_return_pct"),
                ))
            db.commit()
            return report.id
        finally:
            db.close()


orchestrator = Orchestrator()
