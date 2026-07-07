"""
Adil deger hesaplama motoru.
Modeller: Graham Number, DCF, Peter Lynch, P/E karsilastirmasi, Ensemble.
"""
import yfinance as yf
import numpy as np


def graham_number(eps: float, bvps: float) -> dict:
    """Benjamin Graham Number = sqrt(22.5 * EPS * BVPS).
    22.5 = 15 (max P/E) * 1.5 (max P/B)."""
    if eps <= 0 or bvps <= 0:
        return {"value": None, "method": "Graham Number", "error": "EPS veya BVPS negatif/0 — Graham uygulanamaz"}
    fair = np.sqrt(22.5 * eps * bvps)
    return {
        "value": round(float(fair), 2), "method": "Graham Number",
        "inputs": {"eps": round(eps, 2), "bvps": round(bvps, 2)},
        "formula": "sqrt(22.5 * EPS * BVPS)",
    }


def peter_lynch_fair_value(eps: float, eps_growth_pct: float, dividend_yield_pct: float = 0) -> dict:
    """Peter Lynch Fair Value = EPS * (EPS growth + dividend yield).
    PEG ratio <= 1 is considered undervalued."""
    if eps <= 0:
        return {"value": None, "method": "Peter Lynch", "error": "EPS negatif"}
    growth = eps_growth_pct
    ratio = eps_growth_pct + dividend_yield_pct
    fair = eps * ratio if ratio > 0 else eps * 15  # fallback
    peg = (fair / eps) / growth if growth > 0 else 99
    return {
        "value": round(float(fair), 2), "method": "Peter Lynch Fair Value",
        "inputs": {"eps": round(eps, 2), "eps_growth": round(eps_growth_pct, 1), "div_yield": round(dividend_yield_pct, 1)},
        "peg_ratio": round(peg, 2), "formula": "EPS * (Growth% + DivYield%)",
    }


def dcf_fair_value(fcf_per_share: float, shares_outstanding: float = None,
                   growth_rate: float = 0.08, terminal_growth: float = 0.025,
                   wacc: float = 0.09, projection_years: int = 5) -> dict:
    """Indirgenmis Nakit Akisi (DCF) modeli.
    FCF projekte edilir → WACC ile bugune indirgenir + terminal deger."""
    if fcf_per_share <= 0:
        return {"value": None, "method": "DCF", "error": "Serbest nakit akisi negatif — DCF uygulanamaz"}

    pv_sum = 0.0
    fcf = fcf_per_share
    for yr in range(1, projection_years + 1):
        fcf *= (1 + growth_rate)
        pv = fcf / ((1 + wacc) ** yr)
        pv_sum += pv

    # Terminal value (Gordon Growth)
    terminal_fcf = fcf * (1 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1 + wacc) ** projection_years)

    fair = pv_sum + pv_terminal

    return {
        "value": round(float(fair), 2), "method": "DCF (Indirgenmis Nakit Akisi)",
        "inputs": {
            "fcf_per_share": round(fcf_per_share, 2), "growth_rate_pct": round(growth_rate * 100, 1),
            "wacc_pct": round(wacc * 100, 1), "terminal_growth_pct": round(terminal_growth * 100, 1),
            "projection_years": projection_years,
        },
        "formula": "Σ(FCF_t / (1+WACC)^t) + TV / (1+WACC)^n",
    }


def pe_based_fair_value(eps: float, sector_avg_pe: float = 18.0) -> dict:
    """Sektor ortalama P/E'sine gore adil deger."""
    if eps <= 0:
        return {"value": None, "method": "P/E Karsilastirmasi", "error": "EPS negatif"}
    fair = eps * sector_avg_pe
    return {
        "value": round(float(fair), 2), "method": "P/E Karsilastirmasi",
        "inputs": {"eps": round(eps, 2), "sector_pe": round(sector_avg_pe, 1)},
        "formula": "EPS * Sektor Ortalama F/K",
    }


# Sektor ortalama P/E degerleri
SECTOR_PE_AVG = {
    "Technology": 28, "Consumer Electronics": 25, "Semiconductors": 22,
    "Software": 30, "Financial Services": 14, "Banking": 12,
    "Insurance": 13, "Healthcare": 22, "Biotechnology": 35,
    "Energy": 12, "Oil & Gas": 10, "Consumer Cyclical": 20,
    "Consumer Defensive": 22, "Retail": 22, "Industrials": 18,
    "Aerospace & Defense": 22, "Real Estate": 20, "Utilities": 16,
    "Communication Services": 18, "Basic Materials": 14,
    "Transportation": 16, "Automotive": 10, "Telecom": 14, "Media": 16,
}


def get_sector_pe(sector: str) -> float:
    for key, val in SECTOR_PE_AVG.items():
        if key.lower() in (sector or "").lower():
            return float(val)
    return 18.0


def ensemble_fair_value(values: list[dict], current_price: float) -> dict:
    """Coklu model agirlikli ortalama."""
    valid = [v for v in values if v.get("value") is not None and v["value"] > 0]
    if not valid:
        return {"fair_value": None, "current_price": current_price, "models": values}

    weights = {"Graham Number": 0.25, "Peter Lynch": 0.25, "DCF": 0.30, "P/E Karsilastirmasi": 0.20}
    use = [v for v in valid if 0.05 * current_price < v["value"] < 5 * current_price]
    if len(use) < 2:
        use = valid  # az model varsa hepsini kullan

    weights = {"Graham Number": 0.15, "Peter Lynch": 0.20, "DCF": 0.40, "P/E Karsilastirmasi": 0.25}
    weighted_sum = 0.0
    weight_total = 0.0
    for v in use:
        w = weights.get(v["method"], 0.25)
        weighted_sum += v["value"] * w
        weight_total += w

    fair = weighted_sum / weight_total if weight_total > 0 else 0
    margin = round((fair / current_price - 1) * 100, 1) if current_price > 0 else 0

    return {
        "fair_value": round(float(fair), 2),
        "current_price": round(float(current_price), 2),
        "margin_pct": margin,
        "assessment": "Asiri degerli" if margin < -20 else "Dusuk degerli" if margin > 20 else "Adil degerde" if abs(margin) < 10 else "Hafif " + ("dusuk" if margin > 0 else "yuksek") + " degerli",
        "models": valid,
    }


def calculate_fair_value(ticker_str: str) -> dict:
    """Bir hisse icin tum modelleri calistir."""
    t = yf.Ticker(ticker_str)
    info = t.info or {}

    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
    eps = info.get("trailingEps")
    if eps is None or eps <= 0:
        eps = info.get("forwardEps") or 1.0

    bvps = info.get("bookValue")
    if bvps is None:
        equity = info.get("totalStockholderEquity") or 0
        shares = info.get("sharesOutstanding") or 1
        bvps = equity / shares if shares > 0 else 1.0

    fcf = info.get("freeCashflow") or 0
    shares = info.get("sharesOutstanding") or 1
    fcf_per_share = fcf / shares if shares > 0 and fcf > 0 else eps * 0.5

    growth = info.get("earningsGrowth") or info.get("revenueGrowth") or 0.08
    if isinstance(growth, (int, float)) and growth > 0:
        growth_pct = float(growth) * 100 if growth < 1 else float(growth)
    else:
        growth_pct = 8.0

    div_yield = info.get("dividendYield") or 0.0
    if isinstance(div_yield, (int, float)) and div_yield > 0:
        div_pct = float(div_yield) * 100 if div_yield < 1 else float(div_yield)
    else:
        div_pct = 0.0

    sector = info.get("sector") or ""
    sector_pe = get_sector_pe(sector)

    models = [
        graham_number(eps, bvps),
        peter_lynch_fair_value(eps, growth_pct, div_pct),
        dcf_fair_value(fcf_per_share, growth_rate=growth_pct / 100 if growth_pct > 0 else 0.08),
        pe_based_fair_value(eps, sector_pe),
    ]

    result = ensemble_fair_value(models, price)

    # Gercek verileri ekle
    result["ticker"] = ticker_str.upper()
    result["metrics"] = {
        "eps": round(eps, 2) if eps else None,
        "bvps": round(bvps, 2) if bvps else None,
        "fcf_per_share": round(fcf_per_share, 2),
        "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "sector": sector,
        "sector_avg_pe": sector_pe,
        "dividend_yield": info.get("dividendYield"),
        "growth_rate": round(growth_pct, 1),
    }

    return result
