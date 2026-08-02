"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../lib/api";
import type { LiveWatchlistItem, LivePortfolio } from "../lib/api";

type LivePricesState = {
  watchlist: LiveWatchlistItem[];
  portfolio: LivePortfolio | null;
  error: string | null;
};

const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

/**
 * Canlı fiyat akışı — SSE (Server-Sent Events).
 *
 * Backend `/api/prices/stream?portfolio_slug=X` her 3s'de {watchlist, portfolio}
 * gönderir. EventSource otomatik reconnect yapar; 3s REST polling yerine tek
 * bağlantı (ANALIZ_RAPORU M9). API_KEY header gönderemez — query param ile verilir
 * (backend middleware api_key query param kabul eder).
 */
export function useLivePrices(portfolioSlug: "bist" | "us"): LivePricesState {
  const [watchlist, setWatchlist] = useState<LiveWatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<LivePortfolio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const params = new URLSearchParams({ portfolio_slug: portfolioSlug });
    if (API_KEY) params.set("api_key", API_KEY);
    const url = `${API_BASE}/api/prices/stream?${params.toString()}`;

    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("prices", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as {
          watchlist: LiveWatchlistItem[];
          portfolio: LivePortfolio | null;
        };
        setWatchlist(Array.isArray(data.watchlist) ? data.watchlist : []);
        setPortfolio(data.portfolio ?? null);
        setError(null);
      } catch {
        setError("Canlı fiyat verisi çözümlenemedi.");
      }
    });

    es.onerror = () => {
      // EventSource otomatik yeniden bağlanır — kullanıcıya durumu göster.
      setError("Canlı fiyat bağlantısı kesildi — yeniden bağlanılıyor…");
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [portfolioSlug]);

  return { watchlist, portfolio, error };
}
