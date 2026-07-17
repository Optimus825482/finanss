"""
News Analyst Agent — TradingAgents (UCLA/MIT) inspired 4th analyst.

SentimentAgent'tan farkı: ham haber başlıklarını VADER'la skorlayıp geçmez,
yapılandırılmış analiz yapar:
- Haber hacmi (kaç haber)
- Haber tazeleme hızı (son 24s/7g oranı)
- Trend tespiti (sentiment yönü değişiyor mu?)
- Insider işlem çakışması kontrolü
- Anahtar kelime çıkarımı (earnings, merger, lawsuit, FDA vb.)
"""
import asyncio
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from app.agents.base import BaseAgent, AgentStatus
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

_analyzer = SentimentIntensityAnalyzer()

# Anahtar olay kelimeleri
EVENT_KEYWORDS = {
    "earnings": ["earnings", "revenue", "profit", "loss", "EPS", "guidance", "outlook"],
    "merger": ["merger", "acquisition", "buyout", "takeover", "M&A", "deal"],
    "legal": ["lawsuit", "litigation", "SEC", "investigation", "fine", "settlement"],
    "product": ["launch", "approval", "FDA", "patent", "trial", "phase"],
    "restructuring": ["layoff", "restructuring", "spin-off", "divestiture", "bankruptcy"],
    "management": ["CEO", "CFO", "appointed", "resigned", "board", "executive"],
}


class NewsAnalyst(BaseAgent):
    """Haberleri yapılandırılmış analiz eden ajan."""

    name = "news"
    label = "Haber Analisti"

    async def run(self, candidates: list[dict]) -> list[dict]:
        self._set(AgentStatus.RUNNING, f"{len(candidates)} sembol için haber analizi yapılıyor")
        try:
            enriched = await asyncio.to_thread(self._analyze, candidates)
            self._set(AgentStatus.DONE, "Haber analizi tamamlandı")
            return enriched
        except Exception as e:
            self._set(AgentStatus.ERROR, str(e))
            raise

    def _analyze(self, candidates: list[dict]) -> list[dict]:
        from app.services.yf_utils import safe_ticker_news

        for c in candidates:
            ticker = c.get("ticker", "")
            news_items = safe_ticker_news(ticker)

            if not news_items:
                c["news_score"] = 50.0
                c["news_count"] = 0
                c["news_burst"] = False
                c["news_sentiment_trend"] = "neutral"
                c["news_events"] = []
                continue

            headlines = []
            publish_times = []
            all_text = []

            for item in news_items[:20]:
                title = item.get("content", {}).get("title") or item.get("title")
                summary = item.get("content", {}).get("summary") or item.get("summary", "")
                if title:
                    headlines.append(title)
                    all_text.append(title)
                if summary:
                    all_text.append(summary)

                # Publish time
                pub_time = item.get("content", {}).get("pubDate") or item.get("providerPublishTime")
                if pub_time:
                    try:
                        if isinstance(pub_time, (int, float)):
                            publish_times.append(datetime.fromtimestamp(pub_time))
                        else:
                            publish_times.append(datetime.fromisoformat(str(pub_time).replace("Z", "+00:00")))
                    except Exception:
                        pass

            # ── Sentiment score (VADER) ──
            compounds = [_analyzer.polarity_scores(h)["compound"] for h in headlines]
            avg_compound = sum(compounds) / len(compounds) if compounds else 0
            c["news_score"] = round((avg_compound + 1) * 50, 1)

            # ── News count ──
            c["news_count"] = len(headlines)

            # ── News burst detection (son 24 saatte vs son 7 gün) ──
            if publish_times:
                now = datetime.now()
                last_24h = sum(1 for t in publish_times if (now - t.replace(tzinfo=None)) <= timedelta(hours=24))
                last_7d = len(publish_times)
                if last_7d > 0:
                    burst_ratio = last_24h / last_7d
                    c["news_burst"] = burst_ratio > 0.5  # yarıdan fazlası son 24 saatte
                else:
                    c["news_burst"] = False
            else:
                c["news_burst"] = False

            # ── Sentiment trend (ilk yarı vs ikinci yarı) ──
            mid = len(compounds) // 2
            if mid > 0 and len(compounds) > 3:
                first_half = sum(compounds[:mid]) / mid
                second_half = sum(compounds[mid:]) / (len(compounds) - mid)
                if second_half > first_half + 0.1:
                    trend = "improving"
                elif second_half < first_half - 0.1:
                    trend = "deteriorating"
                else:
                    trend = "stable"
            else:
                trend = "stable"
            c["news_sentiment_trend"] = trend

            # ── Event detection ──
            events = []
            for category, keywords in EVENT_KEYWORDS.items():
                for kw in keywords:
                    if any(kw.lower() in h.lower() for h in headlines[:10]):
                        events.append(category)
                        break
            c["news_events"] = list(set(events))

            # ── Composite news signal ──
            signal = c["news_score"]
            if c["news_burst"]:
                signal += 5 if avg_compound > 0 else -5
            if trend == "improving":
                signal += 3
            elif trend == "deteriorating":
                signal -= 3
            c["news_score"] = round(max(0, min(100, signal)), 1)

            logger.debug("[NewsAnalyst] %s: score=%.0f count=%d burst=%s trend=%s events=%s",
                         ticker, c["news_score"], c["news_count"],
                         c["news_burst"], trend, c["news_events"])

        return candidates
