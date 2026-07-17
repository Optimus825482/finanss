"""
RD-Agent style factor extraction: Agent Team ciktisindan yapilandirilmis
faktor, sinyal ve model input'u cikaran servis.

RD-Agent pattern: Research (veri topla) -> Development (faktor cikar -> modelle).
"""
import hashlib
from datetime import datetime
from app.config import now_istanbul
from typing import Optional

from app.database import SessionLocal
from app.models.memory import ResearchMemory


def extract_factors_from_candidate(candidate: dict) -> dict:
    """Bir candidate sozlugunden Qlib/RD-Agent formatinda faktor sozlugu cikar."""
    factors = {}

    # Fiyat faktoru
    if candidate.get("price"):
        factors["price"] = float(candidate["price"])

    # Momentum faktoru
    if candidate.get("momentum_pct") is not None:
        factors["momentum"] = float(candidate["momentum_pct"])

    # Temel faktorler (FundamentalAgent'tan)
    if candidate.get("pe_ratio") is not None:
        factors["pe_ratio"] = float(candidate["pe_ratio"])
    if candidate.get("pb_ratio") is not None:
        factors["pb_ratio"] = float(candidate["pb_ratio"])
    if candidate.get("roe") is not None:
        factors["roe"] = float(candidate["roe"])
    if candidate.get("debt_to_equity") is not None:
        factors["debt_to_equity"] = float(candidate["debt_to_equity"])
    if candidate.get("peg_ratio") is not None:
        factors["peg_ratio"] = float(candidate["peg_ratio"])
    if candidate.get("fcf_yield") is not None:
        factors["fcf_yield"] = float(candidate["fcf_yield"])

    # Risk faktorleri (RiskAgent'tan)
    if candidate.get("volatility_annualized") is not None:
        factors["volatility"] = float(candidate["volatility_annualized"])
    if candidate.get("max_drawdown_pct") is not None:
        factors["drawdown"] = float(candidate["max_drawdown_pct"])
    if candidate.get("beta") is not None:
        factors["beta"] = float(candidate["beta"])

    # Skorlar
    if candidate.get("fundamental_score") is not None:
        factors["fundamental_score"] = float(candidate["fundamental_score"])
    if candidate.get("sentiment_score") is not None:
        factors["sentiment_score"] = float(candidate["sentiment_score"])
    if candidate.get("risk_score") is not None:
        factors["risk_score"] = float(candidate["risk_score"])
    if candidate.get("composite_score") is not None:
        factors["composite_score"] = float(candidate["composite_score"])

    # Narrative embedding potansiyeli (sonradan vektor DB'ye)
    if candidate.get("narrative"):
        factors["narrative_hash"] = hashlib.sha256(candidate["narrative"].encode()).hexdigest()[:12]

    return factors


def extract_and_store_factors(
    ticker: str, candidates: list[dict], summary: str,
    source_report_id: Optional[int] = None,
):
    """RD-Agent R+D pipeline: tum candidate'lerden faktor cikar ve memory'e kaydet."""
    db = SessionLocal()
    try:
        stored = []
        for c in candidates:
            factors = extract_factors_from_candidate(c)
            memory = ResearchMemory(
                ticker=ticker.upper(),
                topic="factor_extraction",
                summary=f"RD-Agent faktor cikarimi: {len(factors)} faktor",
                data_snapshot=factors,
                source_report_id=source_report_id,
                confidence=0.65,
                created_at=now_istanbul(),
            )
            db.add(memory)
            db.flush()
            stored.append({"id": memory.id, "ticker": ticker, "factor_count": len(factors)})

        db.commit()
        return stored
    except Exception:
        db.rollback()
        return []
    finally:
        db.close()


def get_factor_history(ticker: str, limit: int = 10) -> list[dict]:
    """Bir hisse icin gecmis faktor verilerini getir (Qlib timeline benzeri)."""
    db = SessionLocal()
    try:
        memories = (
            db.query(ResearchMemory)
            .filter(
                ResearchMemory.ticker == ticker.upper(),
                ResearchMemory.topic == "factor_extraction",
            )
            .order_by(ResearchMemory.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": m.id,
                "ticker": m.ticker,
                "factors": m.data_snapshot or {},
                "confidence": m.confidence,
                "created_at": m.created_at.isoformat(),
            }
            for m in memories
        ]
    finally:
        db.close()
