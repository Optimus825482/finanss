# Live Dashboard Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ana sayfa üst kısmına canlı takip listesi ve canlı portföy durumu ekle; SSE ile 3 saniyede bir güncelle.

**Architecture:** Backend'de `sse-starlette` ile tek SSE endpoint (`/api/prices/stream`), frontend'de `EventSource` kullanan `useLivePrices` hook. WatchlistBar ve PortfolioStatusBar yeni bileşenleri dashboard'un en üstüne yerleşir, Hero banner kalkar.

**Tech Stack:** FastAPI + sse-starlette (backend), Next.js 14 + React 18 + EventSource (frontend)

---

### Task 1: Backend SSE prices endpoint

**Files:**
- Create: `backend/app/routers/prices.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add sse-starlette dependency**

```bash
cd backend && pip install sse-starlette
```

Then add to `backend/requirements.txt` — append after line 22 (`matplotlib>=3.8.0`):

```
sse-starlette>=2.0.0
```

- [ ] **Step 2: Create prices router**

Create `backend/app/routers/prices.py`:

```python
"""Canlı fiyat SSE (Server-Sent Events) endpoint'i.
Watchlist ve otonom ajan portföyü fiyatlarını 3 saniyede bir push'lar.
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models import WatchlistItem
from app.services.market_data import get_live_prices
from app.services.autonomous_agent import AutonomousAgent

router = APIRouter(prefix="/api/prices", tags=["prices"])
logger = logging.getLogger(__name__)

VALID_SLUGS = ("bist", "us")


async def _fetch_prices(db: Session, portfolio_slug: str) -> dict:
    """Watchlist + otonom portföy fiyatlarını tek hamlede çek."""
    # Watchlist
    wl_items = db.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()
    wl_tickers = [i.ticker for i in wl_items]
    wl_prices = (
        await asyncio.to_thread(get_live_prices, wl_tickers) if wl_tickers else {}
    )
    watchlist = [
        {
            "id": i.id,
            "ticker": i.ticker,
            "price": wl_prices.get(i.ticker, {}).get("price"),
            "change_pct": wl_prices.get(i.ticker, {}).get("change_pct"),
            "notes": i.notes,
        }
        for i in wl_items
    ]

    # Otonom ajan portföyü
    portfolio = None
    try:
        agent = AutonomousAgent(portfolio_slug=portfolio_slug)
        p = agent.get_portfolio(db)
        portfolio = {
            "cash": p.get("cash", 0),
            "position_count": p.get("position_count", 0),
            "total_cost": p.get("total_cost", 0),
            "total_market_value": p.get("total_market_value", 0),
            "total_pl": p.get("total_pl", 0),
            "total_pl_pct": p.get("total_pl_pct", 0),
            "positions": [
                {
                    "id": pos.get("id"),
                    "ticker": pos.get("ticker"),
                    "quantity": pos.get("quantity"),
                    "entry_price": pos.get("entry_price"),
                    "current_price": pos.get("current_price"),
                    "unrealized_pl": pos.get("unrealized_pl", 0),
                }
                for pos in p.get("positions", [])
            ],
        }
    except Exception as e:
        logger.warning(f"Portfolio fetch failed: {e}")

    return {"watchlist": watchlist, "portfolio": portfolio}


@router.get("/stream")
async def stream_prices(
    request: Request,
    portfolio_slug: str = Query("bist", description="bist | us"),
    db: Session = Depends(get_db),
):
    """SSE fiyat akışı — her 3 saniyede bir watchlist + portföy durumu."""

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await _fetch_prices(db, portfolio_slug)
                yield {"event": "prices", "data": json.dumps(data, default=str)}
            except Exception as e:
                logger.error(f"SSE fetch error: {e}")
                yield {"event": "error", "data": json.dumps({"error": str(e)})}
            await asyncio.sleep(3)

    return EventSourceResponse(event_generator())
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/prices.py backend/requirements.txt
git commit -m "feat: add SSE /api/prices/stream endpoint"
```

---

### Task 2: Register prices router in backend

**Files:**
- Modify: `backend/app/routers/__init__.py`

- [ ] **Step 1: Add prices import and registration**

In `backend/app/routers/__init__.py`, add `prices` to the import tuple and `app.include_router` call:

**Change the import block (line 3-7):**

```python
from app.routers import (
    reports, watchlist, portfolio, balance, profile, chat, memory, admin,
    screener, screener_analyze, screener_screen, notifications, predictions,
    autonomous, skill, prices,
)
```

**Add after the `autonomous.router` line (line 24) — insert before `skill.router`:**

```python
    app.include_router(prices.router)
```

Result:

```python
    app.include_router(autonomous.router)
    app.include_router(prices.router)
    app.include_router(skill.router)
```

- [ ] **Step 2: Verify router registration**

```bash
cd backend && python -c "from app.routers import register_routers; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/__init__.py
git commit -m "feat: register prices router"
```

---

### Task 3: Frontend LivePrice types

**Files:**
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1: Add LivePrice types to api.ts**

After the existing `WatchlistItem` type (around line 78), add these new types before the `api` object:

```typescript
// ── SSE Live Prices ──

export type LiveWatchlistItem = {
  id: number;
  ticker: string;
  price: number | null;
  change_pct: number | null;
  notes: string | null;
};

export type LivePortfolioPosition = {
  id: number;
  ticker: string;
  quantity: number;
  entry_price: number;
  current_price: number | null;
  unrealized_pl: number;
};

export type LivePortfolio = {
  cash: number;
  position_count: number;
  total_cost: number;
  total_market_value: number;
  total_pl: number;
  total_pl_pct: number;
  positions: LivePortfolioPosition[];
};

export type LivePricesEvent = {
  watchlist: LiveWatchlistItem[];
  portfolio: LivePortfolio | null;
};
```

Insert them right before `async function j<T>` (before line 283).

- [ ] **Step 2: Commit**

```bash
git add frontend/app/lib/api.ts
git commit -m "feat: add LivePrice SSE types"
```

---

### Task 4: useLivePrices hook

**Files:**
- Create: `frontend/app/hooks/useLivePrices.ts`

- [ ] **Step 1: Create the hook**

Create `frontend/app/hooks/useLivePrices.ts`:

```typescript
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { LiveWatchlistItem, LivePortfolio } from "../lib/api";

type LivePricesState = {
  watchlist: LiveWatchlistItem[];
  portfolio: LivePortfolio | null;
  error: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8012";

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

    const url = `${API_BASE}/api/prices/stream?portfolio_slug=${portfolioSlug}`;
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/hooks/useLivePrices.ts
git commit -m "feat: add useLivePrices SSE hook"
```

---

### Task 5: WatchlistBar component

**Files:**
- Create: `frontend/app/components/WatchlistBar.tsx`

- [ ] **Step 1: Create WatchlistBar component**

Create `frontend/app/components/WatchlistBar.tsx`:

```typescript
"use client";

import Link from "next/link";
import type { LiveWatchlistItem } from "../lib/api";

interface WatchlistBarProps {
  items: LiveWatchlistItem[];
}

/** BIST hisseleri .IS ile biter — ₺, diğerleri $ */
function currencySymbol(ticker: string): string {
  return ticker.endsWith(".IS") ? "₺" : "$";
}

export default function WatchlistBar({ items }: WatchlistBarProps) {
  if (items.length === 0) {
    return (
      <div
        className="rounded-sm px-4 py-3 mb-4 text-center font-mono text-xs"
        style={{
          backgroundColor: "var(--term-panel)",
          border: "1px solid var(--term-border)",
          color: "var(--term-muted)",
        }}
      >
        Takip listeniz boş.{" "}
        <Link href="/takip" style={{ color: "var(--term-amber)" }}>
          /takip sayfasından hisse ekleyin →
        </Link>
      </div>
    );
  }

  return (
    <div
      className="rounded-sm mb-4"
      style={{
        backgroundColor: "var(--term-panel)",
        border: "1px solid var(--term-border)",
      }}
    >
      <div className="flex items-center justify-between px-4 py-2">
        <div
          className="text-[11px] tracking-[0.2em] font-mono"
          style={{ color: "var(--term-muted)" }}
        >
          TAKİP LİSTESİ
        </div>
        <Link
          href="/takip"
          className="text-xs font-mono transition-none"
          style={{ color: "var(--term-amber)" }}
        >
          TÜMÜNÜ GÖR →
        </Link>
      </div>
      <div className="flex gap-2 px-4 pb-3 overflow-x-auto">
        {items.map((it) => {
          const sym = currencySymbol(it.ticker);
          const change = it.change_pct ?? 0;
          const isUp = change >= 0;
          return (
            <Link
              key={it.id}
              href="/takip"
              className="rounded-sm px-3 py-2 text-center transition-none shrink-0 min-w-[90px] block"
              style={{
                backgroundColor: "var(--term-bg)",
                border: "1px solid var(--term-border)",
              }}
            >
              <div
                className="font-mono text-sm font-semibold"
                style={{ color: "var(--term-text)" }}
              >
                {it.ticker.replace(".IS", "")}
              </div>
              {it.price !== null ? (
                <div
                  className="font-mono text-xs mt-0.5"
                  style={{ color: "var(--term-text)" }}
                >
                  {sym}
                  {it.price.toFixed(2)}
                  <span
                    className="ml-1"
                    style={{
                      color: isUp ? "var(--term-green)" : "var(--term-red)",
                    }}
                  >
                    {isUp ? "▲" : "▼"}
                    {Math.abs(change).toFixed(1)}%
                  </span>
                </div>
              ) : (
                <div
                  className="text-xs font-mono mt-0.5"
                  style={{ color: "var(--term-muted)" }}
                >
                  —
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/components/WatchlistBar.tsx
git commit -m "feat: add WatchlistBar component"
```

---

### Task 6: PortfolioStatusBar component

**Files:**
- Create: `frontend/app/components/PortfolioStatusBar.tsx`

- [ ] **Step 1: Create PortfolioStatusBar component**

Create `frontend/app/components/PortfolioStatusBar.tsx`:

```typescript
"use client";

import type { LivePortfolio } from "../lib/api";

interface PortfolioStatusBarProps {
  portfolio: LivePortfolio | null;
  slug: "bist" | "us";
  onToggle: (slug: "bist" | "us") => void;
}

const sym = "₺";

export default function PortfolioStatusBar({
  portfolio,
  slug,
  onToggle,
}: PortfolioStatusBarProps) {
  const borderColor = "var(--term-border)";

  return (
    <div
      className="rounded-sm mb-4"
      style={{
        backgroundColor: "var(--term-panel)",
        border: `1px solid ${borderColor}`,
      }}
    >
      {/* Header row — toggle + label */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ borderBottom: `1px solid ${borderColor}` }}
      >
        <div className="flex items-center gap-3">
          <div
            className="text-[11px] tracking-[0.2em] font-mono"
            style={{ color: "var(--term-muted)" }}
          >
            PORTFÖY DURUMU
          </div>
          <div className="flex gap-1">
            {(["bist", "us"] as const).map((s) => (
              <button
                key={s}
                onClick={() => onToggle(s)}
                className="font-mono text-[10px] tracking-wider px-2 py-0.5 rounded-sm transition-none"
                style={{
                  border: "1px solid var(--term-border)",
                  backgroundColor:
                    slug === s ? "var(--term-border)" : "var(--term-bg)",
                  color:
                    slug === s ? "var(--term-amber)" : "var(--term-muted)",
                }}
              >
                {s === "bist" ? "BIST" : "US"}
              </button>
            ))}
          </div>
        </div>
        <div
          className="text-[10px] font-mono"
          style={{ color: "var(--term-muted)" }}
        >
          CANLI · 3sn
        </div>
      </div>

      {!portfolio ? (
        <div
          className="px-4 py-3 text-center font-mono text-xs"
          style={{ color: "var(--term-muted)" }}
        >
          Ajan başlatılıyor… İlk çalıştırmada portföy oluşur.
        </div>
      ) : (
        <>
          {/* Özet grid */}
          <div className="grid grid-cols-4 gap-2 px-4 py-3">
            <div className="text-center">
              <div
                className="text-[9px] font-mono tracking-wider"
                style={{ color: "var(--term-muted)" }}
              >
                NAKİT
              </div>
              <div
                className="font-mono text-sm font-semibold"
                style={{ color: "var(--term-text)" }}
              >
                {sym}
                {portfolio.cash.toLocaleString("tr-TR", {
                  minimumFractionDigits: 2,
                })}
              </div>
            </div>
            <div className="text-center">
              <div
                className="text-[9px] font-mono tracking-wider"
                style={{ color: "var(--term-muted)" }}
              >
                POZİSYON
              </div>
              <div
                className="font-mono text-sm font-semibold"
                style={{ color: "var(--term-text)" }}
              >
                {portfolio.position_count}
              </div>
            </div>
            <div className="text-center">
              <div
                className="text-[9px] font-mono tracking-wider"
                style={{ color: "var(--term-muted)" }}
              >
                PİYASA D.
              </div>
              <div
                className="font-mono text-sm font-semibold"
                style={{ color: "var(--term-text)" }}
              >
                {sym}
                {portfolio.total_market_value.toLocaleString("tr-TR", {
                  minimumFractionDigits: 2,
                })}
              </div>
            </div>
            <div className="text-center">
              <div
                className="text-[9px] font-mono tracking-wider"
                style={{ color: "var(--term-muted)" }}
              >
                P/L
              </div>
              <div
                className="font-mono text-sm font-semibold"
                style={{
                  color:
                    portfolio.total_pl >= 0
                      ? "var(--term-green)"
                      : "var(--term-red)",
                }}
              >
                {portfolio.total_pl >= 0 ? "+" : ""}
                {sym}
                {portfolio.total_pl.toLocaleString("tr-TR", {
                  minimumFractionDigits: 2,
                })}{" "}
                <span className="text-[10px]">
                  (%{portfolio.total_pl_pct.toFixed(1)})
                </span>
              </div>
            </div>
          </div>

          {/* Mini pozisyon listesi (ilk 3) */}
          {portfolio.positions.length > 0 && (
            <div style={{ borderTop: `1px solid ${borderColor}` }}>
              <div className="flex gap-3 px-4 py-2 overflow-x-auto">
                {portfolio.positions.slice(0, 3).map((pos) => (
                  <div
                    key={pos.id}
                    className="font-mono text-[11px] shrink-0"
                    style={{ color: "var(--term-text)" }}
                  >
                    <span className="font-semibold">
                      {pos.ticker.replace(".IS", "")}
                    </span>{" "}
                    <span style={{ color: "var(--term-muted)" }}>
                      x{pos.quantity}
                    </span>{" "}
                    <span
                      style={{
                        color:
                          pos.unrealized_pl >= 0
                            ? "var(--term-green)"
                            : "var(--term-red)",
                      }}
                    >
                      {pos.unrealized_pl >= 0 ? "+" : ""}
                      {sym}
                      {pos.unrealized_pl.toFixed(0)}
                    </span>
                  </div>
                ))}
                {portfolio.positions.length > 3 && (
                  <span
                    className="font-mono text-[11px] shrink-0"
                    style={{ color: "var(--term-muted)" }}
                  >
                    +{portfolio.positions.length - 3} daha
                  </span>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/components/PortfolioStatusBar.tsx
git commit -m "feat: add PortfolioStatusBar component"
```

---

### Task 7: Refactor dashboard page.tsx

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Replace page.tsx with new layout**

Replace the entire content of `frontend/app/page.tsx`:

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import {
  api,
  PipelineStatus,
  Report,
  ReportListItem,
} from "./lib/api";
import { useLivePrices } from "./hooks/useLivePrices";
import SignalChain from "./components/SignalChain";
import StockCard from "./components/StockCard";
import WatchlistBar from "./components/WatchlistBar";
import PortfolioStatusBar from "./components/PortfolioStatusBar";
import ErrorBoundary from "./components/ErrorBoundary";

export default function Dashboard() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [history, setHistory] = useState<ReportListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [portfolioSlug, setPortfolioSlug] = useState<"bist" | "us">("bist");

  // Live prices via SSE
  const { watchlist, portfolio, error: liveError } =
    useLivePrices(portfolioSlug);

  const refreshStatus = useCallback(async () => {
    try {
      const s = await api.getStatus();
      setStatus(s);
      return s;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Bilinmeyen hata";
      setError(
        `Backend'e bağlanılamadı: ${msg}. http://localhost:8012 çalışıyor mu?`
      );
      return null;
    }
  }, []);

  const refreshReport = useCallback(async () => {
    try {
      const r = await api.getLatestReport();
      setReport(r);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Bilinmeyen hata";
      if (!msg.includes("404")) setError(`Rapor alınamadı: ${msg}`);
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const h = await api.getHistory();
      setHistory(h);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Bilinmeyen hata";
      setError(`Geçmiş yüklenemedi: ${msg}`);
    }
  }, []);

  // Initial loading — only status/report/history (SSE is independent)
  useEffect(() => {
    Promise.all([refreshStatus(), refreshReport(), refreshHistory()]).finally(
      () => setInitialLoading(false)
    );
  }, [refreshStatus, refreshReport, refreshHistory]);

  // Poll status while pipeline is running
  useEffect(() => {
    if (!status?.running) return;
    const interval = setInterval(async () => {
      const s = await refreshStatus();
      if (s && !s.running) {
        refreshReport();
        refreshHistory();
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [status?.running, refreshStatus, refreshReport, refreshHistory]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      await api.generate();
      await refreshStatus();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Bilinmeyen hata";
      setError(`Rapor başlatılamadı: ${msg}`);
    } finally {
      setGenerating(false);
    }
  };

  const loadReport = async (id: number) => {
    try {
      const r = await api.getReport(id);
      setReport(r);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Bilinmeyen hata";
      setError(`Rapor yüklenemedi: ${msg}`);
    }
  };

  return (
    <ErrorBoundary>
      <main className="min-h-screen px-6 py-6 max-w-6xl mx-auto">
        {/* ========== CANLI BÖLÜM ========== */}
        {/* Watchlist — her zaman göster, SSE'den canlı */}
        <WatchlistBar items={watchlist} />

        {/* Portfolio — SSE'den canlı */}
        <PortfolioStatusBar
          portfolio={portfolio}
          slug={portfolioSlug}
          onToggle={setPortfolioSlug}
        />

        {/* Canlı fiyat hatası (SSE koparsa) */}
        {liveError && (
          <div
            className="text-xs px-4 py-2 rounded-sm mb-4 font-mono"
            style={{
              backgroundColor: "rgba(220, 38, 38, 0.1)",
              color: "var(--term-red)",
              border: "1px solid var(--term-red)",
            }}
          >
            {liveError}
          </div>
        )}

        {/* ========== RAPOR BÖLÜMÜ ========== */}

        {/* Rapor üret butonu bar */}
        <div
          className="scanline rounded-sm px-4 py-3 mb-4 flex items-center justify-between"
          style={{
            backgroundColor: "var(--term-panel)",
            border: "1px solid var(--term-border)",
          }}
        >
          <div>
            <div
              className="font-mono text-[11px] tracking-[0.2em]"
              style={{ color: "var(--term-amber)" }}
            >
              ORBIS FINANCE ANALYZE TEAM
            </div>
            <p
              className="text-xs mt-0.5"
              style={{ color: "var(--term-muted)" }}
            >
              {report
                ? new Date(report.created_at).toLocaleString("tr-TR")
                : "henüz rapor yok"}
            </p>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating || status?.running}
            className="font-mono text-xs tracking-wider px-4 py-2 rounded-sm transition-none disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              border: "1px solid var(--term-amber)",
              color: "var(--term-amber)",
            }}
          >
            {status?.running ? "PIPELINE ÇALIŞIYOR…" : "▶ RAPORU ŞİMDİ ÜRET"}
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div
            className="text-sm px-4 py-3 rounded-sm mb-4 font-mono"
            style={{
              backgroundColor: "rgba(220, 38, 38, 0.1)",
              color: "var(--term-red)",
              border: "1px solid var(--term-red)",
            }}
          >
            {error}
          </div>
        )}

        {/* Initial loading */}
        {initialLoading && !error && (
          <div
            className="mb-4 rounded-sm p-8 text-center font-mono text-sm"
            style={{
              color: "var(--term-muted)",
              border: "1px dashed var(--term-border)",
            }}
          >
            Veriler yükleniyor…
          </div>
        )}

        {/* Signal chain */}
        {!initialLoading && status && (
          <div className="mb-4">
            <SignalChain agents={status.agents} />
          </div>
        )}

        {/* Report grid + history sidebar */}
        {!initialLoading && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3 space-y-6">
              {report && (
                <div
                  className="rounded-sm p-4"
                  style={{
                    backgroundColor: "var(--term-panel)",
                    border: "1px solid var(--term-border)",
                  }}
                >
                  <div
                    className="text-[11px] tracking-[0.2em] font-mono mb-2"
                    style={{ color: "var(--term-muted)" }}
                  >
                    GÜNLÜK ÖZET
                  </div>
                  <p
                    className="text-sm leading-relaxed"
                    style={{ color: "var(--term-text)" }}
                  >
                    {report.summary}
                  </p>
                  <div
                    className="text-[10px] font-mono mt-2"
                    style={{ color: "var(--term-muted)" }}
                  >
                    {report.candidates_scanned} sembol tarandı ·{" "}
                    {report.picks.length} öneri
                  </div>
                </div>
              )}

              {report && report.picks.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {report.picks.map((pick, idx) => (
                    <StockCard
                      key={pick.ticker}
                      pick={pick}
                      rank={idx + 1}
                      showPredict={false}
                    />
                  ))}
                </div>
              ) : (
                !status?.running &&
                !initialLoading && (
                  <div
                    className="border border-dashed rounded-sm p-10 text-center font-mono text-sm"
                    style={{
                      borderColor: "var(--term-border)",
                      color: "var(--term-muted)",
                    }}
                  >
                    Henüz rapor üretilmedi. "RAPORU ŞİMDİ ÜRET" ile ilk taramayı
                    başlat.
                  </div>
                )
              )}
            </div>

            <div className="lg:col-span-1">
              <div
                className="rounded-sm p-4 sticky top-20"
                style={{
                  backgroundColor: "var(--term-panel)",
                  border: "1px solid var(--term-border)",
                }}
              >
                <div
                  className="text-[11px] tracking-[0.2em] font-mono mb-3"
                  style={{ color: "var(--term-muted)" }}
                >
                  RAPOR GEÇMİŞİ
                </div>
                <div className="space-y-1">
                  {history.length === 0 && (
                    <div
                      className="text-xs font-mono"
                      style={{ color: "var(--term-muted)" }}
                    >
                      Kayıt yok
                    </div>
                  )}
                  {history.map((h) => (
                    <button
                      key={h.id}
                      onClick={() => loadReport(h.id)}
                      className="w-full text-left px-2 py-2 rounded-sm font-mono text-xs transition-none"
                      style={{
                        backgroundColor:
                          report?.id === h.id
                            ? "var(--term-border)"
                            : "transparent",
                        color:
                          report?.id === h.id
                            ? "var(--term-amber)"
                            : "var(--term-text)",
                      }}
                    >
                      <div>
                        {new Date(h.created_at).toLocaleDateString("tr-TR")}
                      </div>
                      <div style={{ color: "var(--term-muted)" }}>
                        {h.top_ticker || "—"} · {h.candidates_scanned} sembol
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </ErrorBoundary>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: live dashboard — WatchlistBar + PortfolioStatusBar with SSE"
```

---

## Verification Checklist

After all tasks complete, run these checks:

```bash
# 1. Backend starts clean
cd backend && venv/Scripts/activate && python -c "from app.main import app; print('Backend OK')"

# 2. SSE endpoint returns stream (test with curl for 5s)
curl -s -N --max-time 5 "http://localhost:8012/api/prices/stream?portfolio_slug=bist"

# 3. Frontend builds clean
cd frontend && npx next build 2>&1 | tail -5

# 4. TypeScript check
cd frontend && npx tsc --noEmit
```

Expected: SSE stream should return `event: prices` with `data: {"watchlist":[...], "portfolio":{...}}` JSON. Frontend build should succeed with zero errors.
