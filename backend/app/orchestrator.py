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

    async def run_deep_pipeline(self, exchanges: list[str] | None = None) -> int:
        """Deep Batch modu: Stage 2 sonrası her pick için Fair Value + Prediction + LLM."""
        if self.is_running:
            raise RuntimeError("Pipeline zaten calisiyor")

        self.is_running = True
        self.last_error = None
        self.progress_log = []
        self.exchanges = exchanges or []

        try:
            return await self._run_deep(exchanges)
        except Exception as e:
            self.last_error = str(e)
            raise
        finally:
            self.is_running = False

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

        # LLM enrichment per pick (concurrent)
        try:
            from app.agents.report_agent import _llm_enrich_pick
            enriched = await _asyncio.gather(*[_llm_enrich_pick(p) for p in top_picks], return_exceptions=True)
            for i, result in enumerate(enriched):
                if not isinstance(result, Exception) and result:
                    top_picks[i] = result
        except Exception:
            pass

        # Build summary
        for c in top_picks:
            c["narrative"] = (
                f"{c['ticker']}: composite {c.get('composite_score', 0):.0f}, "
                f"{c.get('valuation_assessment', 'degerleme yok')}"
            )
            if c.get("llm_reasoning"):
                c["narrative"] += f" — {c['llm_reasoning'][:200]}"

        summary_lines = [f"Deep Batch Raporu: {total_scanned} hisse tarandi, {len(top_picks)} pick secildi."]
        best = top_picks[0] if top_picks else None
        if best:
            summary_lines.append(f"En guclu: {best['ticker']} ({best.get('composite_score', 0):.0f}/100)")
        result = {"summary": "\n".join(summary_lines), "candidates_scanned": total_scanned, "picks": top_picks}

        rid = self._persist(result)
        self._log(f"Deep Rapor #{rid} kaydedildi ({len(top_picks)} pick)")
        return rid

    def _persist(self, result: dict) -> int:
        db = SessionLocal()
        try:
            report = Report(created_at=datetime.utcnow(), summary=result["summary"],
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
