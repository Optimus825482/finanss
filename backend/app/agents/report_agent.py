"""
ReportAgent (Rapor)
Tüm ajanlardan gelen verileri sentezleyip teknik dil kullanmayan,
her yatirimcinin anlayabilecegi Turkce rapor uretir.
LLM destekli zenginlestirme.
"""
import asyncio

from app.agents.base import BaseAgent, AgentStatus
from app.config import SCORING_WEIGHTS, TOP_N_PICKS


def _narrative_for(c: dict) -> str:
    """Kisa ozet — LLM yoksa kullanilir."""
    ticker = c["ticker"]
    parts = [f"{ticker} son hafta %{c['momentum_pct']:.1f} {'yukari' if c['momentum_pct'] > 0 else 'asagi'} hareket etti"]

    if c.get("pe_ratio"):
        pe = c["pe_ratio"]
        if pe < 15: parts.append(f"F/K orani {pe:.1f} ile sektorune gore ucuz")
        elif pe < 30: parts.append(f"F/K orani {pe:.1f} ile degerlemesi normal")
        else: parts.append(f"F/K orani {pe:.1f} ile yuksek degerlemede")

    fs = c.get("fundamental_score", 50)
    if fs >= 70: parts.append("bilanco ve gelir tablosu oldukca guclu")
    elif fs >= 50: parts.append("finansal tablolar orta seviyede")
    elif fs >= 30: parts.append("bazi finansal gostergeler zayif")

    ss = c.get("sentiment_score", 50)
    if ss >= 65: parts.append("piyasa ve medya olumlu")
    elif ss <= 35: parts.append("haber akisi ve duygu temkinli")

    rs = c.get("risk_score", 50)
    if rs <= 35: parts.append("fiyat hareketleri sakin, risk dusuk")
    elif rs >= 65: parts.append("fiyat hareketleri sert, yuksek volatilite")

    return ". ".join(parts) + "."


def _build_rich_summary(candidates: list[dict], top_picks: list[dict]) -> str:
    """LLM destekli zengin Turkce rapor ozeti."""
    if not top_picks:
        return "Bugun tarama kriterlerini gecen bir aday bulunamadi. Piyasa genel olarak durgun."

    total = len(candidates)
    best = top_picks[0]
    avg_fundamental = sum(p["fundamental_score"] for p in top_picks) / len(top_picks)
    avg_sentiment = sum(p["sentiment_score"] for p in top_picks) / len(top_picks)
    avg_risk = sum(p["risk_score"] for p in top_picks) / len(top_picks)

    risk_desc = "dusuk" if avg_risk <= 40 else "orta" if avg_risk <= 60 else "yuksek"
    sentiment_desc = "olumlu" if avg_sentiment >= 55 else "karisik" if avg_sentiment >= 40 else "temkinli"

    lines = [
        f"Bugun {total} hisse senedi tarandi.",
        f"Bunlar arasindan {len(top_picks)} tanesi compozit puani en yuksek cikanlar olarak onerildi.",
        "",
        f"En guclu aday: {best['ticker']} ({best['composite_score']:.0f}/100 compozit puan)",
        f"  • Guncel fiyat: ${best.get('price', 0):.2f}",
        f"  • Son hafta degisim: %{best.get('momentum_pct', 0):.1f}",
        f"  • Temel analiz puani: {best.get('fundamental_score', 0):.0f}/100",
        f"  • Duygu/haber puani: {best.get('sentiment_score', 0):.0f}/100",
        f"  • Risk puani: {best.get('risk_score', 0):.0f}/100 (ne kadar dusuk o kadar iyi)",
    ]

    if best.get("pe_ratio"):
        lines.append(f"  • F/K orani: {best['pe_ratio']:.1f}")
    if best.get("volatility_annualized"):
        lines.append(f"  • Yillik volatilite: %{best['volatility_annualized']:.1f}")
    if best.get("max_drawdown_pct"):
        lines.append(f"  • En buyuk dusus: %{best['max_drawdown_pct']:.1f}")

    lines.extend([
        "",
        f"Genel degerlendirme:",
        f"  • Secilen hisselerin ortalama temel analiz puani: {avg_fundamental:.0f}/100",
        f"  • Ortalama haber duygu durumu: {sentiment_desc} ({avg_sentiment:.0f}/100)",
        f"  • Ortalama risk seviyesi: {risk_desc} ({avg_risk:.0f}/100)",
        "",
        f"Not: Bu bir yatirim tavsiyesi degildir. Piyasa kosullari hizla degisebilir.",
        f"Kendi arastirmanizi yaparak karar vermeniz onerilir.",
    ])

    return "\n".join(lines)


async def _llm_enrich(summary: str) -> str:
    """LLM ile ozeti daha okunakli hale getir (varsa)."""
    try:
        from app.services.llm_bridge import generate
        prompt = f"""Asagidaki finansal rapor ozetini, teknik terim kullanmadan, bir arkadasina anlatir gibi,
herkesin anlayabilecegi sade bir Turkce ile tekrar yaz. Kisa ve net olsun.
Rakamlari ve onemli verileri koru. 'Yatirim tavsiyesi degildir' uyarisini ekle.

Rapor:
{summary}"""

        result = await generate(prompt=prompt, temperature=0.5, max_tokens=512)
        return result.strip() if result and len(result) > 20 else summary
    except Exception:
        return summary


class ReportAgent(BaseAgent):
    name = "report"
    label = "Rapor"

    async def run(self, candidates: list[dict]) -> dict:
        self._set(AgentStatus.RUNNING, "Skorlar birlestiriliyor, rapor yaziliyor")
        try:
            result = await asyncio.to_thread(self._compose, candidates)
            # LLM zenginlestirme (async)
            try:
                enriched = await _llm_enrich(result["summary"])
                result["summary"] = enriched
            except Exception:
                pass
            self._set(AgentStatus.DONE, f"{len(result['picks'])} hisse onerisiyle rapor hazir")
            return result
        except Exception as e:
            self._set(AgentStatus.ERROR, str(e))
            raise

    def _compose(self, candidates: list[dict]) -> dict:
        w = SCORING_WEIGHTS
        for c in candidates:
            risk_inverse = 100 - c["risk_score"]
            c["composite_score"] = round(
                c["fundamental_score"] * w["fundamental"]
                + c["sentiment_score"] * w["sentiment"]
                + risk_inverse * w["risk"],
                1,
            )
            c["narrative"] = _narrative_for(c)

        candidates.sort(key=lambda x: x["composite_score"], reverse=True)
        top_picks = candidates[:TOP_N_PICKS]

        summary = _build_rich_summary(candidates, top_picks)
        return {"summary": summary, "candidates_scanned": len(candidates), "picks": top_picks}
