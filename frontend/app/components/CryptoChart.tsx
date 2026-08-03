"use client";

import { useEffect, useRef } from "react";
import {
  createChart, IChartApi, ISeriesApi, ColorType, CrosshairMode,
  CandlestickSeries, LineSeries, HistogramSeries, Time,
} from "lightweight-charts";
import type { CryptoKline } from "../lib/api";

type Props = {
  klines: CryptoKline[];
  height?: number;
};

// ── Teknik hesaplama (PriceChart ile aynı mantık) ──
function smaArr(d: number[], p: number): (number | null)[] {
  const o: (number | null)[] = [];
  for (let i = 0; i < d.length; i++) {
    if (i < p - 1) { o.push(null); continue; }
    let s = 0;
    for (let j = i - p + 1; j <= i; j++) s += d[j];
    o.push(s / p);
  }
  return o;
}
function emaArr(d: number[], p: number): (number | null)[] {
  const o: (number | null)[] = [];
  const k = 2 / (p + 1);
  for (let i = 0; i < d.length; i++) {
    if (i === 0) { o.push(d[0]); continue; }
    const pr = o[i - 1] ?? d[i];
    o.push(d[i] * k + pr * (1 - k));
  }
  return o;
}
function bollinger(d: number[], p: number, m: number) {
  const mid = smaArr(d, p);
  const up: (number | null)[] = [];
  const lo: (number | null)[] = [];
  for (let i = 0; i < d.length; i++) {
    if (i < p - 1) { up.push(null); lo.push(null); continue; }
    let s = 0;
    for (let j = i - p + 1; j <= i; j++) s += (d[j] - mid[i]!) ** 2;
    const std = Math.sqrt(s / p);
    up.push(mid[i]! + m * std);
    lo.push(mid[i]! - m * std);
  }
  return { upper: up, middle: mid, lower: lo };
}
function rsiFn(d: number[], p: number): (number | null)[] {
  const o: (number | null)[] = [];
  let ag = 0, al = 0;
  for (let i = 1; i < d.length; i++) {
    const ch = d[i] - d[i - 1];
    const gn = ch > 0 ? ch : 0;
    const ls = ch < 0 ? -ch : 0;
    if (i < p) {
      ag += gn; al += ls;
      if (i !== p - 1) { o.push(null); continue; }
      ag /= p; al /= p;
    } else {
      ag = (ag * (p - 1) + gn) / p;
      al = (al * (p - 1) + ls) / p;
    }
    o.push(ag === 0 && al === 0 ? 50 : al === 0 ? 100 : 100 - (100 / (1 + ag / al)));
  }
  return o;
}
function macdFn(d: number[]) {
  const e12 = emaArr(d, 12);
  const e26 = emaArr(d, 26);
  const mv: (number | null)[] = [];
  for (let i = 0; i < d.length; i++) mv.push(e12[i] != null && e26[i] != null ? e12[i]! - e26[i]! : null);
  const sigVals = emaArr(mv.filter(v => v != null) as number[], 9);
  const sig: (number | null)[] = [];
  const off = 26 + 9 - 2;
  for (let i = 0; i < d.length; i++) sig.push(i < off ? null : sigVals[i - off] ?? null);
  const hs: (number | null)[] = [];
  for (let i = 0; i < d.length; i++) hs.push(mv[i] != null && sig[i] != null ? mv[i]! - sig[i]! : null);
  return { macd: mv, signal: sig, hist: hs };
}
// StochRSI: RSI → (rsi - min)/(max - min) over L(=14) window, then SMA(3)
function stochRsiFn(d: number[], rsiP = 14, stochL = 14, kSmooth = 3): (number | null)[] {
  const r = rsiFn(d, rsiP);
  const o: (number | null)[] = [];
  for (let i = 0; i < d.length; i++) {
    if (r[i] == null || i < stochL - 1) { o.push(null); continue; }
    let mn = Infinity, mx = -Infinity;
    for (let j = i - stochL + 1; j <= i; j++) {
      const v = r[j]!;
      if (v < mn) mn = v;
      if (v > mx) mx = v;
    }
    o.push(mx === mn ? 0.5 : (r[i]! - mn) / (mx - mn));
  }
  return smaArr(o as number[], kSmooth);
}

/**
 * Kripto M5 mum grafiği — lightweight-charts v5.
 * Ana pane: candlestick + default Bollinger Bands (20, 2σ).
 * Alt paneler: MACD (pane 1) + StochRSI (pane 2).
 */
export default function CryptoChart({ klines, height = 320 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<ISeriesApi<any>[]>([]);

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

    seriesRefs.current = [];
    chartRef.current = chart;

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
      seriesRefs.current = [];
    };
  }, [height]);

  // Klines değişince tüm serileri (candle + BB + MACD + StochRSI) güncelle
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const data = klines.map((k) => ({
      time: Math.floor(k.open_time / 1000) as Time,
      open: k.open,
      high: k.high,
      low: k.low,
      close: k.close,
    }));
    const closes = klines.map((k) => k.close);

    // Ana pane (0): candlestick + Bollinger Bands
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e", downColor: "#ef4444",
      borderUpColor: "#22c55e", borderDownColor: "#ef4444",
      wickUpColor: "#22c55e", wickDownColor: "#ef4444",
      priceLineVisible: false,
    }, 0);
    candle.setData(data);

    const bb = bollinger(closes, 20, 2);
    const bbSeries = [
      ["BB_UP", "#f59e0b", bb.upper],
      ["BB_MID", "#eab308", bb.middle],
      ["BB_LOW", "#f59e0b", bb.lower],
    ] as const;
    bbSeries.forEach(([, color, vals]) => {
      const s = chart.addSeries(LineSeries, {
        color, lineWidth: 1, priceLineVisible: false, lastValueVisible: true,
      }, 0);
      s.setData(vals.map((v, i) => v == null ? null : { time: data[i].time, value: v }).filter((x): x is NonNullable<typeof x> => x != null));
      seriesRefs.current.push(s);
    });

    // Pane 1: MACD (histogram + line + signal)
    const { macd: mv, signal: sig, hist: hs } = macdFn(closes);
    const macdLine = chart.addSeries(LineSeries, {
      color: "#f59e0b", lineWidth: 1, priceLineVisible: false, lastValueVisible: true,
    }, 1);
    macdLine.setData(mv.map((v, i) => v == null ? null : { time: data[i].time, value: v }).filter((x): x is NonNullable<typeof x> => x != null));
    const sigLine = chart.addSeries(LineSeries, {
      color: "#3b82f6", lineWidth: 1, priceLineVisible: false, lastValueVisible: true,
    }, 1);
    sigLine.setData(sig.map((v, i) => v == null ? null : { time: data[i].time, value: v }).filter((x): x is NonNullable<typeof x> => x != null));
    const hist = chart.addSeries(HistogramSeries, {
      priceLineVisible: false, lastValueVisible: false,
    }, 1);
    hist.setData(hs.map((v, i) => v == null ? null : {
      time: data[i].time,
      value: v,
      color: v >= 0 ? "rgba(34,197,94,0.5)" : "rgba(239,68,68,0.5)",
    }).filter((x): x is NonNullable<typeof x> => x != null));

    // Pane 2: StochRSI
    const stoch = stochRsiFn(closes);
    const stochLine = chart.addSeries(LineSeries, {
      color: "#a855f7", lineWidth: 1, priceLineVisible: false, lastValueVisible: true,
    }, 2);
    stochLine.setData(stoch.map((v, i) => v == null ? null : { time: data[i].time, value: v }).filter((x): x is NonNullable<typeof x> => x != null));
    // 20/80 referans çizgileri
    [0.8, 0.2].forEach((level) => {
      const rf = chart.addSeries(LineSeries, {
        color: "rgba(120,113,108,0.4)", lineWidth: 1, lineStyle: 2 as any,
        priceLineVisible: false, lastValueVisible: false,
      }, 2);
      rf.setData(data.map(d => ({ time: d.time, value: level })));
      seriesRefs.current.push(rf);
    });

    seriesRefs.current.push(candle, macdLine, sigLine, hist, stochLine);

    chart.timeScale().fitContent();
  }, [klines]);

  return <div ref={containerRef} style={{ width: "100%", height }} />;
}