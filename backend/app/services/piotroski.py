"""
Piotroski F-Score (0-9) — Value Stock Quality Check.

9 kriterli finansal sağlık skoru:
  Profitability (0-4): Net Income, ROA, Operating CF, CF > NI
  Leverage/Liquidity (0-3): Debt ratio azalış, Current ratio artış, Share dilution
  Operating Efficiency (0-2): Gross margin artış, Asset turnover artış

F-Score >= 7: güçlü değer hissesi (value trap değil)
F-Score <= 3: zayıf temeller — yüksek risk
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _safe_float(val, default=None):
    """None-safe float conversion."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def compute_piotroski(info: dict, prev_info: Optional[dict] = None) -> dict:
    """yfinance ticker.info'dan Piotroski F-Score hesapla.

    prev_info: bir önceki yılın finansal verileri (mümkünse).
    Olmadığında sadece cari yıl kriterleri puanlanır.

    Returns: {"f_score": int, "details": {...}, "grade": str}
    """
    score = 0
    details = {}

    # ── Profitability (0-4) ──

    # 1. Net Income > 0
    net_income = _safe_float(info.get("netIncomeToCommon"))
    if net_income is not None and net_income > 0:
        score += 1
        details["net_income_positive"] = True
    else:
        details["net_income_positive"] = False

    # 2. ROA > 0
    roa = _safe_float(info.get("returnOnAssets"))
    if roa is not None and roa > 0:
        score += 1
        details["roa_positive"] = True
    else:
        details["roa_positive"] = False

    # 3. Operating Cash Flow > 0
    ocf = _safe_float(info.get("operatingCashflow"))
    if ocf is not None and ocf > 0:
        score += 1
        details["ocf_positive"] = True
    elif ocf is not None:
        details["ocf_positive"] = False
    else:
        details["ocf_positive"] = None  # data missing

    # 4. Operating CF > Net Income (earnings quality)
    if ocf is not None and net_income is not None and ocf > net_income:
        score += 1
        details["cf_gt_ni"] = True
    else:
        details["cf_gt_ni"] = False if (ocf is not None and net_income is not None) else None

    # ── Leverage / Liquidity (0-3) ──

    # 5. Long-term Debt to Assets — decreasing vs previous year
    debt_to_assets = _safe_float(info.get("debtToEquity"))
    # debtToEquity decreasing is better
    if prev_info and debt_to_assets is not None:
        prev_de = _safe_float(prev_info.get("debtToEquity"))
        if prev_de is not None and debt_to_assets < prev_de:
            score += 1
            details["debt_decreasing"] = True
        else:
            details["debt_decreasing"] = False
    elif debt_to_assets is not None and debt_to_assets < 100:
        # No prev year: düşük borç = olumlu
        score += 1
        details["debt_decreasing"] = True
    else:
        details["debt_decreasing"] = None

    # 6. Current Ratio increasing (liquidity improving)
    current_ratio = _safe_float(info.get("currentRatio"))
    if prev_info and current_ratio is not None:
        prev_cr = _safe_float(prev_info.get("currentRatio"))
        if prev_cr is not None and current_ratio > prev_cr:
            score += 1
            details["current_ratio_increasing"] = True
        else:
            details["current_ratio_increasing"] = False
    elif current_ratio is not None and current_ratio > 1.0:
        # No prev year: > 1 is healthy
        score += 1
        details["current_ratio_increasing"] = True
    else:
        details["current_ratio_increasing"] = None

    # 7. No new shares issued (dilution check)
    shares_outstanding = _safe_float(info.get("sharesOutstanding"))
    if prev_info and shares_outstanding is not None:
        prev_shares = _safe_float(prev_info.get("sharesOutstanding"))
        if prev_shares is not None and shares_outstanding <= prev_shares:
            score += 1
            details["no_dilution"] = True
        else:
            details["no_dilution"] = False
    elif shares_outstanding is not None:
        # No prev data: assume ok
        score += 1
        details["no_dilution"] = None

    # ── Operating Efficiency (0-2) ──

    # 8. Gross Margin increasing
    gross_margin = _safe_float(info.get("grossMargins"))
    if prev_info and gross_margin is not None:
        prev_gm = _safe_float(prev_info.get("grossMargins"))
        if prev_gm is not None and gross_margin > prev_gm:
            score += 1
            details["gross_margin_increasing"] = True
        else:
            details["gross_margin_increasing"] = False
    elif gross_margin is not None and gross_margin > 0.2:
        # No prev: >20% gross margin is decent
        score += 1
        details["gross_margin_increasing"] = True
    else:
        details["gross_margin_increasing"] = None

    # 9. Asset Turnover increasing
    asset_turnover = _safe_float(info.get("revenuePerShare"))
    total_assets = _safe_float(info.get("totalAssets"))
    shares = _safe_float(info.get("sharesOutstanding"))
    if asset_turnover is not None and total_assets and shares:
        # revenue per share / (assets per share)
        current_at = asset_turnover / (total_assets / shares) if total_assets > 0 and shares > 0 else None
    else:
        current_at = None

    if prev_info and current_at is not None:
        prev_rps = _safe_float(prev_info.get("revenuePerShare"))
        prev_ta = _safe_float(prev_info.get("totalAssets"))
        prev_sh = _safe_float(prev_info.get("sharesOutstanding"))
        if prev_rps and prev_ta and prev_sh and prev_ta > 0 and prev_sh > 0:
            prev_at = prev_rps / (prev_ta / prev_sh)
            if current_at > prev_at:
                score += 1
                details["asset_turnover_increasing"] = True
            else:
                details["asset_turnover_increasing"] = False
        else:
            details["asset_turnover_increasing"] = None
    elif current_at is not None and current_at > 0.5:
        score += 1
        details["asset_turnover_increasing"] = True
    else:
        details["asset_turnover_increasing"] = None

    # Grade
    if score >= 8:
        grade = "A+"
    elif score >= 7:
        grade = "A"
    elif score >= 5:
        grade = "B"
    elif score >= 3:
        grade = "C"
    else:
        grade = "D"

    return {
        "f_score": score,
        "grade": grade,
        "details": details,
    }
