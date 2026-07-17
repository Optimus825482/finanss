"""Haber Sinyal Tarama — şirket haber sinyal tarayıcı.

Kaynak: stock_analysis skill'in rumorScanner.ts port. yfinance `.news` + VADER
sentiment + LLM sınıflandırma. 5 sinyal tipi (impact skor):

| Tip        | Impact | Açıklama |
|------------|--------|----------|
| ma         | +5     | M&A, satınalma, teklif |
| insider    | +4     | CEO/directör alım-satım |
| analyst    | +3     | rating hedef fiyat değişimi |
| regulatory | +3     | SEC/uyum riski |
| earnings   | +2     | earnings öngörü/uyarı |

Dedup: aynı başlık + URL aynı pencerede tekrar etmesin.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.services.llm_bridge import generate
from app.services.web_search import fetch_rumor_format
from app.services.yf_utils import safe_ticker_news
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

_VADER = SentimentIntensityAnalyzer()

# Signal tipi → impact
_IMPACT_MAP: dict[str, int] = {
    "ma": 5,
    "insider": 4,
    "analyst": 3,
    "regulatory": 3,
    "earnings": 2,
}

VALID_TYPES = tuple(_IMPACT_MAP.keys())


# --- Pure fonksiyonlar (test edilebilir) ---

def impact_for_type(signal_type: str) -> int:
    """Signal tipi → impact skor. Bilinmeyen tip → 0."""
    return _IMPACT_MAP.get(signal_type, 0)


def _fingerprint(headline: str, url: Optional[str] = None) -> str:
    """Haber için parmak izi — normalize başlık + url.

    Aynı haber farklı slug ile gelse bile aynı kabul edilir.
    """
    h = re.sub(r"\s+", " ", headline or "").strip().lower()
    u = (url or "").strip().lower()
    raw = f"{h}|{u}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def dedup_signals(
    signals: list[dict],
    window_hours: int = 24,
    now: Optional[datetime] = None,
) -> list[dict]:
    """Aynı parmak izi + window içinde tekrar eden sinyalleri ele.

    En son görülen timestamp'li olanı tutar.
    """
    if not signals:
        return []
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)
    seen: dict[str, dict] = {}
    for s in signals:
        fp = _fingerprint(s.get("headline", ""), s.get("url"))
        ts = s.get("timestamp")
        # Timestamp pencere dışındaysa at
        if ts is not None:
            try:
                ts_dt = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
                if ts_dt.tzinfo is None:
                    ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                if ts_dt < window_start:
                    continue
            except Exception:
                pass
        existing = seen.get(fp)
        if existing is None:
            seen[fp] = s
        else:
            # Daha yüksek impact veya daha yeni timestamp olanı tercih et
            old_imp = impact_for_type(existing.get("signal_type", ""))
            new_imp = impact_for_type(s.get("signal_type", ""))
            if new_imp > old_imp:
                seen[fp] = s
    return list(seen.values())


def _classify_with_vader(title: str, text: str = "") -> tuple[str, str]:
    """VADER sentiment + keyword-bazlı sinyal sınıflandırma (LLM fallback).

    Returns: (signal_type, kısa Türkçe özet)
    """
    # Keyword matching — en yüksek öncelikli
    t_lower = (title + " " + text).lower()
    keyword_map: list[tuple[str, str, str]] = [
        ("merger", "ma"), ("merger", "ma"), ("acquisition", "ma"), ("takeover", "ma"),
        ("bid", "ma"), ("offer", "ma"), ("satın", "ma"), ("birleşme", "ma"),
        ("ceo", "insider"), ("director", "insider"), ("insider", "insider"), ("board", "insider"),
        ("buy shares", "insider"), ("sell shares", "insider"), ("yönetim kurulu", "insider"),
        ("downgrade", "analyst"), ("upgrade", "analyst"), ("target price", "analyst"),
        ("rating", "analyst"), ("analyst", "analyst"), ("hedef fiyat", "analyst"),
        ("sec", "regulatory"), ("investigation", "regulatory"), ("fine", "regulatory"),
        ("lawsuit", "regulatory"), ("regulatory", "regulatory"), ("soruşturma", "regulatory"),
        ("earnings", "earnings"), ("revenue", "earnings"), ("profit", "earnings"),
        ("guidance", "earnings"), ("quarterly", "earnings"), ("kar", "earnings"),
        ("gelir", "earnings"), ("zarar", "earnings"),
    ]
    for kw, sig_type in keyword_map:
        if kw in t_lower:
            return sig_type, f"Keyword tabanlı sınıflandırma: '{kw}' algılandı"

    # Keyword yok → VADER sentiment bazlı
    scores = _VADER.polarity_scores(title)
    compound = scores["compound"]
    if compound > 0.3:
        return "earnings", "Pozitif haber (VADER)"
    elif compound < -0.3:
        return "earnings", "Negatif haber (VADER)"
    return "earnings", "Nötr haber (VADER)"

async def _classify_headlines(
    headlines: list[dict],
    ticker: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> list[dict]:
    """LLM ile haber başlıklarını 5 tipe sınıflandır.

    headlines: yfinance .news formatı — [{"title", "publisher", "link", "providerPublishTime", ...}]
    Returns: [{"headline", "type", "impact", "summary", "source", "url", "timestamp"}]
    """
    if not headlines:
        return []

    # Başlık listesini LLM için paketle
    items = []
    for h in headlines[:20]:  # maksimum 20 haber
        items.append({
            "headline": h.get("title", ""),
            "source": h.get("publisher", ""),
            "url": h.get("link", ""),
        })

    context = f"Hedef ticker: {ticker}" if ticker else "Piyasa geneli"
    prompt = f"""{context} için şu haber başlıklarını sınıflandır.

Kategoriler (sadece bunlardan biri):
- ma: birleşme, satınalma, teklif, M&A
- insider: CEO/directör/insider alım-satım
- analyst: rating değişikliği, hedef fiyat revizyonu
- regulatory: SEC/uyum/düzenleyici soruşturma
- earnings: earnings öngörü, uyarı, guidance

Başlıklar:
{json.dumps(items, ensure_ascii=False, indent=2)}

Çıktı formatı (SADECE JSON, ```json fenced):
```json
[{{"headline": "...", "type": "ma", "summary": "kısa Türkçe özet"}}]
```

Kurallar:
- Sadece verilen başlıkları işle.
- type yukarıdaki 5 değerden biri olmalı.
- summary Türkçe, 1 cümle.
- Uydurma başlık ekleme."""

    try:
        response = await generate(
            prompt=prompt,
            system="Finansal haber sınıflandırma asistanısın. Sadece verilen veriyi kullan, uydurma.",
            temperature=0.2,
            max_tokens=2048,
            model=model,
            api_key=api_key,
            api_base=api_base,
        )
    except Exception as e:
        logger.warning("rumor_scanner: LLM classify failed (%s) — fallback to keyword+VADER", e)
        # Fallback: keyword + VADER sentiment ile sınıflandır
        fallback_signals = []
        for h in headlines[:20]:
            sig_type, summary = _classify_with_vader(h.get("title", ""), h.get("publisher", ""))
            fallback_signals.append({
                "signal_type": sig_type,
                "impact_score": impact_for_type(sig_type),
                "headline": h.get("title", ""),
                "source": h.get("publisher"),
                "url": h.get("link"),
                "timestamp": _parse_ts(h.get("providerPublishTime")),
                "summary": summary,
            })
        return fallback_signals

    # JSON array parse — fenced önce
    m = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", response)
    raw = m.group(1) if m else response
    try:
        from json_repair import repair_json
        parsed = repair_json(raw, return_objects=True)
        if not isinstance(parsed, list):
            parsed = []
    except Exception:
        parsed = []

    # Eşleştir — LLM çıktısıyla orijinal haberleri bul
    by_headline = {h.get("title", ""): h for h in headlines}
    signals = []
    for item in parsed:
        hl = item.get("headline", "")
        original = by_headline.get(hl)
        sig_type = item.get("type", "earnings")
        if sig_type not in VALID_TYPES:
            sig_type = "earnings"
        signals.append({
            "signal_type": sig_type,
            "impact_score": impact_for_type(sig_type),
            "headline": hl,
            "source": (original or {}).get("publisher") if original else None,
            "url": (original or {}).get("link") if original else None,
            "timestamp": _parse_ts((original or {}).get("providerPublishTime")) if original else None,
            "summary": item.get("summary"),
        })
    return signals


def _parse_ts(ts) -> Optional[datetime]:
    """yfinance providerPublishTime (unix epoch int) → datetime."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, OSError):
        return None


# --- Async run wrapper ---

async def run(
    query: Optional[str] = None,
    db=None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> dict:
    """Rumor taraması yürüt — yfinance news + web search + LLM/VADER sınıflandırma.

    model: Ayarlar'dan seçilen rumor_model. None → generate() kendi default'unu kullanır.
    api_key/api_base: DB kayıtlı provider credentials (NVIDIA NIM vb).
    """
    ticker = query.upper().strip() if query else None
    if not ticker:
        # Piyasa geneli tarama — şu an universe'ten ilk 5 ticker'ı tara
        from app.services.screener_service import get_universe
        all_tickers = get_universe()
        ticker = None
        targets = all_tickers[:5] if all_tickers else []
    else:
        targets = [ticker]

    all_signals: list[dict] = []
    for t in targets:
        news = await asyncio.to_thread(safe_ticker_news, t)
        if news:
            signals = await _classify_headlines(news, ticker=t, model=model, api_key=api_key, api_base=api_base)
            all_signals.extend(signals)

        # --- Web search zenginleştirme (anahtarsız kaynaklar) ---
        # DuckDuckGo + Google News + Reddit + HN birleştirilir
        try:
            web_hits = await fetch_rumor_format(
                f"{t} stock news OR earnings OR acquisition OR analyst",
                limit_per_source=5,
            )
            if web_hits:
                web_signals = await _classify_headlines(web_hits, ticker=t, model=model, api_key=api_key, api_base=api_base)
                all_signals.extend(web_signals)
        except Exception as e:
            logger.debug("rumor_scanner web_search %s failed: %s", t, e)

    # Dedup 24h pencere
    deduped = dedup_signals(all_signals, window_hours=24)
    total_impact = sum(s.get("impact_score", 0) for s in deduped)

    return {
        "query": ticker,
        "signals": deduped,
        "total_impact": total_impact,
    }
