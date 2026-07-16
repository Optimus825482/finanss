"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import type { TickerDetailData } from "../components/TickerDetail";
import { apiFetch } from "../lib/api";

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
  const periodRef = useRef(period);
  const intervalRef = useRef(interval_);
  periodRef.current = period;
  intervalRef.current = interval_;

  const fetchDetail = useCallback(async (t: string, p: string, i: string) => {
    try {
      const res = await apiFetch(
        `/api/screener/${encodeURIComponent(t)}?period=${p}&interval=${i}`,
        { cache: "no-store" }
      );
      if (res.ok) setDetail(await res.json());
    } catch (e) {
      console.warn("Failed to fetch detail", e);
    }
  }, []);

  const loadDetail = useCallback(
    (t: string) => {
      currentTicker.current = t;
      setDetailLoading(true);
      setDetail(null);
      fetchDetail(t, periodRef.current, intervalRef.current).finally(() =>
        setDetailLoading(false)
      );
    },
    [fetchDetail]
  );

  // Period/interval değişince yeniden fetch
  useEffect(() => {
    if (currentTicker.current) {
      setDetailLoading(true);
      fetchDetail(currentTicker.current, period, interval_).finally(() =>
        setDetailLoading(false)
      );
    }
  }, [period, interval_, fetchDetail]);

  // Auto-refresh 30s — always rebind with current ticker via ref
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => {
      const t = currentTicker.current;
      if (!t) return;
      fetchDetail(t, periodRef.current, intervalRef.current);
    }, 30_000);
    return () => clearInterval(id);
  }, [autoRefresh, fetchDetail]);

  return {
    detail,
    detailLoading,
    loadDetail,
    period,
    interval: interval_,
    setPeriod,
    setInterval_,
  };
}
