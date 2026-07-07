"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import type { TickerDetailData } from "../components/TickerDetail";

interface UseTickerDetailReturn {
  detail: TickerDetailData | null;
  detailLoading: boolean;
  loadDetail: (t: string) => void;
  period: string;
  interval: string;
  setPeriod: (p: string) => void;
  setInterval_: (i: string) => void;
}

export function useTickerDetail(autoRefresh = true): UseTickerDetailReturn {
  const [detail, setDetail] = useState<TickerDetailData | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [period, setPeriod] = useState("5d");
  const [interval_, setInterval_] = useState("1h");
  const currentTicker = useRef<string | null>(null);
  const autoInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchDetail = useCallback(async (t: string, p: string, i: string) => {
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/screener/${t}?period=${p}&interval=${i}`,
        { cache: "no-store" }
      );
      if (res.ok) setDetail(await res.json());
    } catch { /* sessiz */ }
  }, []);

  const loadDetail = useCallback((t: string) => {
    currentTicker.current = t;
    setDetailLoading(true);
    setDetail(null);
    fetchDetail(t, period, interval_).finally(() => setDetailLoading(false));
  }, [fetchDetail, period, interval_]);

  // Period/interval değişince yeniden fetch
  useEffect(() => {
    if (currentTicker.current) {
      setDetailLoading(true);
      fetchDetail(currentTicker.current, period, interval_).finally(() => setDetailLoading(false));
    }
  }, [period, interval_, fetchDetail]);

  // Auto-refresh 30s
  useEffect(() => {
    if (!autoRefresh) return;
    autoInterval.current = setInterval(() => {
      if (currentTicker.current) {
        fetchDetail(currentTicker.current, period, interval_);
      }
    }, 30_000);
    return () => {
      if (autoInterval.current) clearInterval(autoInterval.current);
    };
  }, [autoRefresh, fetchDetail, period, interval_]);

  return { detail, detailLoading, loadDetail, period, interval: interval_, setPeriod, setInterval_ };
}
