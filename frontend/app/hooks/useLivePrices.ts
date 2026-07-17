"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { LiveWatchlistItem, LivePortfolio } from "../lib/api";

type LivePricesState = {
  watchlist: LiveWatchlistItem[];
  portfolio: LivePortfolio | null;
  error: string | null;
};

export function useLivePrices(portfolioSlug: "bist" | "us"): LivePricesState {
  const [watchlist, setWatchlist] = useState<LiveWatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<LivePortfolio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    // Close existing connection
    if (sourceRef.current) {
      sourceRef.current.close();
    }

    // Relative path → Next.js proxy rewrites /api/* → backend (works in Docker & dev)
    const url = `/api/prices/stream?portfolio_slug=${portfolioSlug}`;
    const es = new EventSource(url);
    sourceRef.current = es;

    es.addEventListener("prices", (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        setWatchlist(data.watchlist || []);
        setPortfolio(data.portfolio);
        setError(null);
      } catch {
        // malformed event, skip
      }
    });

    es.addEventListener("error", () => {
      setError("Canlı fiyat alınamıyor — yeniden bağlanılıyor…");
    });

    es.onerror = () => {
      // EventSource auto-reconnects; update error state
      setError("Canlı fiyat alınamıyor — yeniden bağlanılıyor…");
    };
  }, [portfolioSlug]);

  useEffect(() => {
    connect();
    return () => {
      if (sourceRef.current) {
        sourceRef.current.close();
        sourceRef.current = null;
      }
    };
  }, [connect]);

  return { watchlist, portfolio, error };
}
