"""
ReportAgent (Rapor)
Tüm ajanlardan gelen verileri sentezleyip teknik dil kullanmayan,
her yatirimcinin anlayabilecegi Turkce rapor uretir.
LLM destekli zenginlestirme + Fair Value + Makro baglam.
"""
import asyncio
import logging

from app.agents.base import BaseAgent, AgentStatus
from app.config import SCORING_WEIGHTS, TOP_N_PICKS

logger = logging.getLogger(__name__)


def _currency(c: dict) -> str:
    """BIST hisseleri için ₺, diğerleri için $."""
    return "₺" if c.get("ticker", "").endswith(".IS") else "$"


def _narrative_for(c: dict) -> str:
    """Kisa ozet — LLM yoksa kullanilir. Fair value bilgisi varsa ekler."""
    ticker = c["ticker"]
    mom = c.get("momentum_pct", 0) or 0
    direction = "yukari" if mom > 0 else "asagi" if mom < 0 else "yatay"
    parts = [f"{ticker} son hafta %{mom:.1f} {direction} hareket etti"]

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

    # Fair value baglami
    fv = c.get("fair_value")
    margin = c.get("margin_pct")
    if fv is not None and margin is not None:
        direction = "iskontolu" if margin > 0 else "primli"
        parts.append(f"adil deger {_currency(c)}{fv:.2f} (mevcut fiyata gore %{abs(margin):.1f} {direction})")

    return ". ".join(parts) + "."


def _build_rich_summary(candidates: list[dict], top_picks: list[dict],
                         macro: list[dict] | None = None) -> str:
    """LLM destekli zengin Turkce rapor ozeti — makro baglam dahil."""
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
    ]

    # ── Makro baglam ──
    vix_val = None
    sp500_change = None
    if macro:
        for m in macro:
            if m.get("ticker") == "^VIX" and m.get("price") is not None:
                vix_val = m["price"]
            if m.get("ticker") == "^GSPC" and m.get("change_pct") is not None:
                sp500_change = m["change_pct"]

    if vix_val is not None:
        if vix_val < 15:
            macro_line = f"VIX {vix_val:.1f} ile sakin piyasa (risk-on)"
        elif vix_val < 20:
            macro_line = f"VIX {vix_val:.1f} ile normal piyasa"
        elif vix_val < 30:
            macro_line = f"VIX {vix_val:.1f} ile temkinli piyasa"
        else:
            macro_line = f"VIX {vix_val:.1f} ile panik modu"
        if sp500_change is not None:
            direction = "yukari" if sp500_change > 0 else "asagi"
            macro_line += f", S&P 500 %{sp500_change:+.1f} {direction}"
        lines.append("")
        lines.append(f"🌍 Makro: {macro_line}")

    lines.append("")
    lines.append(f"En guclu aday: {best['ticker']} ({best['composite_score']:.0f}/100 compozit puan)")
    lines.append(f"  • Guncel fiyat: {_currency(best)}{best.get('price', 0):.2f}")
    lines.append(f"  • Son hafta degisim: %{best.get('momentum_pct', 0):.1f}")
    lines.append(f"  • Temel analiz puani: {best.get('fundamental_score', 0):.0f}/100")
    lines.append(f"  • Duygu/haber puani: {best.get('sentiment_score', 0):.0f}/100")
    lines.append(f"  • Risk puani: {best.get('risk_score', 0):.0f}/100 (ne kadar dusuk o kadar iyi)")

    if best.get("pe_ratio"):
        lines.append(f"  • F/K orani: {best['pe_ratio']:.1f}")
    if best.get("volatility_annualized"):
        lines.append(f"  • Yillik volatilite: %{best['volatility_annualized']:.1f}")
    if best.get("max_drawdown_pct"):
        lines.append(f"  • En buyuk dusus: %{best['max_drawdown_pct']:.1f}")
    if best.get("fair_value") and best.get("margin_pct") is not None:
        direction = "iskontolu" if best["margin_pct"] > 0 else "primli"
        lines.append(f"  • Adil deger: {_currency(best)}{best['fair_value']:.2f} (%{abs(best['margin_pct']):.1f} {direction})")

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


async def _llm_enrich_pick(pick: dict) -> dict:
    """Her pick icin LLM gerekcesi + 12 aylik hedef fiyat (varsa). Pick dict mutasyona ugrar."""
    try:
        from app.services.llm_bridge import generate
        import json as _json

        ctx = {
            "ticker": pick.get("ticker"),
            "fundamental_score": pick.get("fundamental_score"),
            "sentiment_score": pick.get("sentiment_score"),
            "risk_score": pick.get("risk_score"),
            "composite_score": pick.get("composite_score"),
            "pe_ratio": pick.get("pe_ratio"),
            "momentum_pct": pick.get("momentum_pct"),
            "price": pick.get("price"),
            "fair_value": pick.get("fair_value"),
            "margin_pct": pick.get("margin_pct"),
        }
        prompt = (
            f"Sen bir hisse senedi analiz asistanisin. Asagidaki verilere dayanarak "
            f"bu hisse icin KISA bir gerekce (2-3 cumle, Turkce) ve skorlara gore "
            f"12 aylik hedef fiyat tahmini yap.\n\n"
            f"Veriler:\n"
        )
        for k, v in ctx.items():
            prompt += f"- {k}: {v}\n"
        prompt += (
            "\nYanit formati (JSON): "
            '{"reasoning": "...", "target_price": 123.45, "expected_return_pct": 12.3}'
            "\nSadece JSON dondur, baska bir sey yazma."
        )
        raw = await generate(prompt=prompt, max_tokens=256, temperature=0.4)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        parsed = _json.loads(raw)
        pick["llm_reasoning"] = str(parsed.get("reasoning", ""))[:300]
        pick["llm_target_price"] = float(parsed["target_price"]) if parsed.get("target_price") else None
        pick["llm_expected_return_pct"] = float(parsed["expected_return_pct"]) if parsed.get("expected_return_pct") else None
        logger.info("pick LLM: %s target=%.2f return=%.1f%%", pick["ticker"],
                     pick["llm_target_price"] or 0, pick["llm_expected_return_pct"] or 0)
    except Exception as e:
        logger.debug("pick LLM failed for %s: %s", pick.get("ticker"), e)
    return pick


class ReportAgent(BaseAgent):
    name = "report"
    label = "Rapor"

    async def run(self, candidates: list[dict]) -> dict:
        self._set(AgentStatus.RUNNING, "Skorlar birlestiriliyor, adil deger hesaplaniyor")
        try:
            result = await self._compose_async(candidates)

            # LLM zenginlestirme — ozet
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
        """Senkron compose — mevcut kodla geri uyumluluk icin."""
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

    async def _compose_async(self, candidates: list[dict]) -> dict:
        """Async compose — Fair Value + Makro + pick LLM eklenmis."""
        w = SCORING_WEIGHTS

        # 1. Composite skor + narrative
        for c in candidates:
            risk_inverse = 100 - c["risk_score"]
            c["composite_score"] = round(
                c["fundamental_score"] * w["fundamental"]
                + c["sentiment_score"] * w["sentiment"]
                + risk_inverse * w["risk"],
                1,
            )

        # 2. Fair Value — her pick icin (concurrent)
        async def _enrich_fv(c: dict) -> dict:
            try:
                from app.services.fair_value import calculate_fair_value as calc_fv
                fv = await asyncio.to_thread(calc_fv, c["ticker"])
                if fv.get("fair_value"):
                    c["fair_value"] = fv["fair_value"]
                    c["margin_pct"] = fv.get("margin_pct")
                    c["valuation_assessment"] = fv.get("assessment")
            except Exception as e:
                logger.debug("fair value failed for %s: %s", c["ticker"], e)
            return c

        enriched = await asyncio.gather(*[_enrich_fv(c) for c in candidates])
        # filter None (olmamasi lazim ama emniyet)
        candidates = [c for c in enriched if c is not None]

        # 3. Narrative olustur (fair value iceren)
        for c in candidates:
            c["narrative"] = _narrative_for(c)

        # 4. Sirala
        candidates.sort(key=lambda x: x["composite_score"], reverse=True)
        top_picks = candidates[:TOP_N_PICKS]

        # 5. Makro gostergeler
        macro = None
        try:
            from app.services.market_data import get_macro_indicators
            macro = await get_macro_indicators()
        except Exception:
            pass

        # 6. Summary (makro baglamli)
        summary = _build_rich_summary(candidates, top_picks, macro=macro)

        # 7. LLM enrichment — her pick icin (concurrent, best-effort)
        try:
            enriched_picks = await asyncio.gather(
                *[_llm_enrich_pick(p) for p in top_picks],
                return_exceptions=True,
            )
            for i, result in enumerate(enriched_picks):
                if not isinstance(result, Exception) and result:
                    top_picks[i] = result
        except Exception:
            pass

        return {"summary": summary, "candidates_scanned": len(candidates), "picks": top_picks}
