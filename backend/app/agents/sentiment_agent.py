"""
SentimentAgent (Haber/Sentiment)
Her aday için güncel haber başlıklarını çeker, VADER ile duygu analizi yapar
ve -1..1 aralığındaki ortalama skoru 0-100 aralığına taşır.
"""
import asyncio
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.agents.base import BaseAgent, AgentStatus

_analyzer = SentimentIntensityAnalyzer()


class SentimentAgent(BaseAgent):
    name = "sentiment"
    label = "Haber/Sentiment"

    async def run(self, candidates: list[dict]) -> list[dict]:
        self._set(AgentStatus.RUNNING, f"{len(candidates)} sembol için haber taranıyor")
        try:
            enriched = await asyncio.to_thread(self._analyze, candidates)
            self._set(AgentStatus.DONE, "Haber/sentiment analizi tamamlandı")
            return enriched
        except Exception as e:
            self._set(AgentStatus.ERROR, str(e))
            raise

    def _analyze(self, candidates: list[dict]) -> list[dict]:
        from app.services.yf_utils import safe_ticker_news
        for c in candidates:
            headlines = []
            news_items = safe_ticker_news(c["ticker"])
            for item in news_items[:10]:
                title = item.get("content", {}).get("title") or item.get("title")
                if title:
                    headlines.append(title)

            if not headlines:
                c["sentiment_score"] = 50.0  # veri yoksa nötr
                c["headline_count"] = 0
                continue

            compounds = [_analyzer.polarity_scores(h)["compound"] for h in headlines]
            avg_compound = sum(compounds) / len(compounds)  # -1..1
            c["sentiment_score"] = round((avg_compound + 1) * 50, 1)  # 0..100
            c["headline_count"] = len(headlines)

        return candidates
