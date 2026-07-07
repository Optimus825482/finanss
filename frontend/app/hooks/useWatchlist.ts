"use client";

import { useState, useEffect, useCallback } from "react";
import { api, WatchlistItem } from "../lib/api";

interface UseWatchlistReturn {
  items: WatchlistItem[];
  loading: boolean;
  error: string | null;
  add: (ticker: string, notes?: string) => Promise<void>;
  remove: (id: number) => Promise<void>;
  reload: () => Promise<void>;
}

export function useWatchlist(): UseWatchlistReturn {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await api.getWatchlist());
    } catch {
      setError("Takip listesi yüklenemedi.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const add = useCallback(async (ticker: string, notes?: string) => {
    await api.addWatchlistItem(ticker, notes);
    await load();
  }, [load]);

  const remove = useCallback(async (id: number) => {
    await api.deleteWatchlistItem(id);
    await load();
  }, [load]);

  return { items, loading, error, add, remove, reload: load };
}
