"""
ScannerAgent (Tarama)
İzlenecek uluslararası hisse evrenini gezer, son fiyat/hacim verisiyle
kaba bir momentum filtresi uygular ve sonraki ajanlara aday listesi devreder.
"""
import asyncio
import yfinance as yf

from app.agents.base import BaseAgent, AgentStatus
from app.config import WATCHLIST, SCANNER_LOOKBACK_DAYS, SCANNER_MIN_MOMENTUM_PCT


class ScannerAgent(BaseAgent):
    name = "scanner"
    label = "Tarama"

    async def run(self) -> list[dict]:
        self._set(AgentStatus.RUNNING, f"{len(WATCHLIST)} sembol taranıyor")
        try:
            candidates = await asyncio.to_thread(self._scan)
            self._set(AgentStatus.DONE, f"{len(candidates)} aday bulundu")
            return candidates
        except Exception as e:
            self._set(AgentStatus.ERROR, str(e))
            raise

    def _scan(self) -> list[dict]:
        results = []
        data = yf.download(
            WATCHLIST,
            period=SCANNER_LOOKBACK_DAYS,
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
        )

        for ticker in WATCHLIST:
            try:
                hist = data[ticker].dropna()
                if hist.empty or len(hist) < 6:
                    continue

                last_close = float(hist["Close"].iloc[-1])
                prev_close_5d = float(hist["Close"].iloc[-6])
                momentum_pct = ((last_close - prev_close_5d) / prev_close_5d) * 100

                avg_volume = float(hist["Volume"].tail(20).mean())
                last_volume = float(hist["Volume"].iloc[-1])
                volume_ratio = (last_volume / avg_volume) if avg_volume > 0 else 1.0

                if momentum_pct < SCANNER_MIN_MOMENTUM_PCT:
                    continue

                results.append({
                    "ticker": ticker,
                    "price": last_close,
                    "momentum_pct": round(momentum_pct, 2),
                    "volume_ratio": round(volume_ratio, 2),
                    "history": hist,  # sonraki ajanlar (risk) için ham veri de taşınır
                })
            except Exception:
                # Tek bir sembolün başarısız olması taramayı durdurmaz
                continue

        # Momentuma göre sırala, en güçlü hareket edenler öne gelsin
        results.sort(key=lambda r: r["momentum_pct"], reverse=True)
        return results
