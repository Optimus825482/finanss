"use client";

import { useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, ColorType, CrosshairMode, CandlestickSeries } from "lightweight-charts";
import type { CryptoKline } from "../lib/api";

type Props = {
  klines: CryptoKline[];
  height?: number;
};

/**
 * Kripto M5 mum grafiği — lightweight-charts v5.
 * OHLC verisinden candlestick serisi çizer. Terminal temasına uygun renkler.
 */
export default function CryptoChart({ klines, height = 320 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;

    const chart = createChart(container, {
      width: container.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#78716c",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(120,113,108,0.08)" },
        horzLines: { color: "rgba(120,113,108,0.08)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "rgba(120,113,108,0.2)" },
      timeScale: { borderColor: "rgba(120,113,108,0.2)", timeVisible: true, secondsVisible: false },
      autoSize: true,
    });

    // v5 API: addSeries(CandlestickSeries, options)
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      if (chartRef.current && container) {
        chartRef.current.applyOptions({ width: container.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height]);

  // Klines değişince seriyi güncelle
  useEffect(() => {
    if (!seriesRef.current) return;
    const data = klines.map((k) => ({
      time: Math.floor(k.open_time / 1000) as any,
      open: k.open,
      high: k.high,
      low: k.low,
      close: k.close,
    }));
    seriesRef.current.setData(data);
  }, [klines]);

  return <div ref={containerRef} style={{ width: "100%", height }} />;
}
