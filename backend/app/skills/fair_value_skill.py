"""Fair Value Skill — adil değer analizi (bağımsız skill).

Mevcut fair_value.py servisini sarmalar, zengin markdown rapor üretir.
4 model (Graham, DCF, Peter Lynch, P/E) + ensemble.
"""
from __future__ import annotations

import asyncio
import logging

from app.services.fair_value import calculate_fair_value as calc_fv

logger = logging.getLogger(__name__)


async def run(ticker: str, db=None) -> dict:
    """Adil değer analizi — 4 model + ensemble.

    Returns:
        {ticker, fair_value, current_price, margin_pct, assessment,
         models, markdown, data_missing}
    """
    ticker = ticker.upper().strip()
    data_missing: list[str] = []

    try:
        fv_result = await asyncio.to_thread(calc_fv, ticker)
    except Exception as e:
        logger.warning("fair_value_skill failed for %s: %s", ticker, e)
        return {
            "ticker": ticker, "fair_value": None, "current_price": None,
            "margin_pct": None, "assessment": "Veri alinamadi", "models": [],
            "markdown": f"# {ticker} — Adil Değer\n\nVERİ ALINAMADI — {e}",
            "data_missing": ["fair_value_calculation"],
        }

    fair_value = fv_result.get("fair_value")
    current_price = fv_result.get("current_price")
    margin_pct = fv_result.get("margin_pct")
    assessment = fv_result.get("assessment", "Veri yok")
    models = fv_result.get("models", [])

    if not models:
        data_missing.append("all_models_failed")
    if fair_value is None:
        data_missing.append("fair_value")

    # Markdown rapor
    md = [f"# {ticker} — Adil Değer Analizi", ""]
    md.append("## 📊 Ensemble Sonuç")
    if fair_value is not None and current_price:
        direction = "iskontolu" if margin_pct and margin_pct > 0 else "primli"
        md.append(f"- **Adil Değer:** ${fair_value:.2f}")
        md.append(f"- **Güncünlük Fiyat:** ${current_price:.2f}")
        md.append(f"- **Marj:** %{margin_pct:+.1f} ({direction})")
        md.append(f"- **Değerlendirme:** {assessment}")
    else:
        md.append("- VERİ YOK")
    md.append("")

    if models:
        md.append("## 🔬 Model Detayları")
        md.append("| Model | Adil Değer |")
        md.append("|---|---|")
        for m in models:
            val = m.get("value")
            method = m.get("method", "N/A")
            if val:
                md.append(f"| {method} | ${val:.2f} |")
            else:
                err = m.get("error", "hesaplanamadi")
                md.append(f"| {method} | ❌ {err} |")
        md.append("")

    md.append("## 📈 Yorum")
    if fair_value and current_price:
        margin = (fair_value / current_price - 1) * 100
        if margin > 20:
            md.append(f"{ticker} mevcut fiyatına göre **%{margin:.1f} iskontolu** — modeller ciddi yükseliş potansiyeli gösteriyor. Ancak bu iskontonun yapısal bir nedeni olabilir (sektör döngüsü, şirkete özgü riskler).")
        elif margin > 5:
            md.append(f"{ticker} **%{margin:.1f} iskontolu** — ılımlı alım fırsatı olabilir.")
        elif margin > -5:
            md.append(f"{ticker} **adil değerine yakın** — %{margin:+.1f} marj ile doğru fiyatlanmış görünüyor.")
        elif margin > -20:
            md.append(f"{ticker} **%{abs(margin):.1f} primli** — piyasa beklentileri fiyatlamış olabilir.")
        else:
            md.append(f"{ticker} **%{abs(margin):.1f} aşırı primli** — dikkatli olunmalı.")
    md.append("")
    md.append("> ⚠️ Bu bir yatırım tavsiyesi değildir. Modeller geçmiş veriye dayanır.")

    return {
        "ticker": ticker,
        "fair_value": fair_value,
        "current_price": current_price,
        "margin_pct": margin_pct,
        "assessment": assessment,
        "models": models,
        "markdown": "\n".join(md),
        "data_missing": data_missing,
    }
