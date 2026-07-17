"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { LiveWatchlistItem, LivePortfolio } from "../lib/api";

type LivePricesState = {
  watchlist: LiveWatchlistItem[];
  portfolio: LivePortfolio | null;
  error: string | null;
};

const POLL_MS = 3000;

export function useLivePrices(portfolioSlug: "bist" | "us"): LivePricesState {
  const [watchlist, setWatchlist] = useState<LiveWatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<LivePortfolio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const slugRef = useRef(portfolioSlug);
  slugRef.current = portfolioSlug;

  const fetchAll = useCallback(async () => {
    try {
      const [wl, pf] = await Promise.all([
        fetch("/api/watchlist/personal").then(r => r.ok ? r.json() : []),
        fetch(`/api/autonomous/portfolio?portfolio_slug=${slugRef.current}`).then(r => r.ok ? r.json() : null),
      ]);
      setWatchlist(Array.isArray(wl) ? wl : []);
      setPortfolio(pf);
      setError(null);
    } catch {
      setError("Canlı fiyat alınamıyor — yeniden bağlanılıyor…");
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const i = setInterval(fetchAll, POLL_MS);
    return () => clearInterval(i);
  }, [fetchAll]);

  return { watchlist, portfolio, error };
}
