# Live Dashboard Redesign — Spec

**Date:** 2026-07-17
**Status:** Approved
**Context:** Ana sayfa layout yeniden düzenlemesi + canlı fiyat akışı

---

## Overview

Dashboard'un üst kısmına **canlı takip listesi** ve **canlı portföy durumu** eklenir. Her ikisi de SSE (Server-Sent Events) ile 3 saniyede bir güncellenir. Hero banner kaldırılır, SignalChain ve rapor grid aşağı kayar.

---

## New Layout (top → bottom)

```
┌──────────────────────────────────────────────┐
│  WATCHLIST BAR  (yatay scroll, 5-10 ticker)  │
├──────────────────────────────────────────────┤
│  PORTFÖY DURUMU  (otonom ajan, BIST/US toggle)│
├──────────────────────────────────────────────┤
│  SIGNAL CHAIN  (5 ajan düğümü)               │
├──────────────────────────────────────────────┤
│  RAPOR GRID + HISTORY SIDEBAR                │
└──────────────────────────────────────────────┘
```

---

## Backend Changes

### 1. New SSE Endpoint: `GET /api/prices/stream`

**File:** `backend/app/routers/prices.py` (new)

**Router prefix:** `/api/prices`

**Dependency:** `sse-starlette` → `backend/requirements.txt`

**Query params:**
- `portfolio_slug` (required): `"bist"` or `"us"`

**Behavior:**
- Her 3 saniyede bir SSE event push'lar
- Event data: `{ "watchlist": [...], "portfolio": {...} }`
- Watchlist: tüm personal watchlist item'ları (ticker, price, change_pct)
- Portfolio: verilen slug'a ait otonom ajan portföyü (cash, positions, totals)
- Kullanıcı auth yok — public endpoint (API_KEY yoksa middleware zaten pas geçiyor)

**Event format:**

```json
{
  "watchlist": [
    {
      "id": 1,
      "ticker": "THYAO.IS",
      "price": 342.50,
      "change_pct": 2.13,
      "notes": null
    }
  ],
  "portfolio": {
    "cash": 12450.00,
    "position_count": 3,
    "total_cost": 52000.00,
    "total_market_value": 55240.00,
    "total_pl": 3240.00,
    "total_pl_pct": 6.23,
    "positions": [
      {
        "id": 1,
        "ticker": "THYAO.IS",
        "quantity": 100,
        "entry_price": 310.00,
        "current_price": 342.50,
        "unrealized_pl": 3250.00
      }
    ]
  }
}
```

**Currency handling:** Backend sends `ticker` as-is (e.g., `THYAO.IS`, `AAPL`). Frontend determines currency by `.IS` suffix.

### 2. Router Registration

**File:** `backend/app/routers/__init__.py`

```python
from app.routers import prices
# ...
app.include_router(prices.router)
```

### 3. Market Data Integration

Use existing `get_live_prices(tickers)` from `app/services/market_data.py`. Watchlist ve portfolio endpoint'leriyle aynı servis.

---

## Frontend Changes

### 1. New Hook: `useLivePrices(portfolioSlug)`

**File:** `frontend/app/hooks/useLivePrices.ts` (new)

```typescript
function useLivePrices(portfolioSlug: "bist" | "us"): {
  watchlist: LiveWatchlistItem[];
  portfolio: LivePortfolio | null;
  error: string | null;
}
```

- `EventSource` ile `GET /api/prices/stream?portfolio_slug=bist` bağlantısı
- Otomatik reconnect (EventSource built-in)
- Cleanup: unmount'ta `close()`
- `portfolioSlug` değişince eski bağlantıyı kapatıp yeni açar

### 2. New Component: `WatchlistBar`

**File:** `frontend/app/components/WatchlistBar.tsx` (new)

**Props:** `{ items: LiveWatchlistItem[] }`

**Render:**
- Yatay scroll container (`overflow-x-auto`)
- Her ticker: kart (ticker, fiyat, % değişim) — mevcut WatchlistWidget kart stiliyle aynı
- BIST ticker'lar `₺`, US ticker'lar `$` prefix
- Pozitif değişim → yeşil, negatif → kırmızı
- Boş state: `"Takip listeniz boş. /takip sayfasından hisse ekleyin."`
- Üst padding yok (dashboard'un en tepesinde), alt padding 16px

**Replaces:** `WatchlistWidget` dashboard'dan kaldırılır (bileşen dosyası silinmez, `/takip` sayfası kullanıyor olabilir).

### 3. New Component: `PortfolioStatusBar`

**File:** `frontend/app/components/PortfolioStatusBar.tsx` (new)

**Props:** `{ portfolio: LivePortfolio; slug: "bist" | "us"; onToggle: (s: string) => void }`

**Render:**
- BIST/US toggle butonları (sol üst)
- Summary row: Nakit | Pozisyon sayısı | Piyasa Değeri | P/L (₺ veya $)
- İsteğe bağlı: ilk 3 pozisyon mini gösterim (ticker + adet + değer)
- P/L pozitif → yeşil, negatif → kırmızı
- `AgentPortfolioCard` dashboard'dan kaldırılır (bileşen dosyası kalır, detay sayfaları kullanabilir)

### 4. Dashboard Refactor: `page.tsx`

**File:** `frontend/app/page.tsx` (modify)

**Changes:**
- Hero banner section kaldırılır
- `useLivePrices("bist")` hook eklenir
- `refreshWatchlist` ve `refreshPortfolio` çağrıları kaldırılır (SSE üzerinden geliyor)
- Layout sıralaması:
  1. `WatchlistBar` (canlı)
  2. `PortfolioStatusBar` (canlı)
  3. SignalChain (mevcut)
  4. Error banner (mevcut)
  5. Report grid + history sidebar (mevcut)
- `AgentPortfolioCard` import'u kaldırılır
- `WatchlistWidget` import'u kaldırılır
- `initialLoading` sadece status/report/history için — SSE verisi bağımsız gelir

### 5. LivePrice Types

**File:** `frontend/app/lib/api.ts` (modify — yeni type'lar)

```typescript
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
```

---

## Files Summary

| File | Action |
|---|---|
| `backend/app/routers/prices.py` | **New** — SSE endpoint |
| `backend/app/routers/__init__.py` | **Modify** — register prices router |
| `backend/requirements.txt` | **Modify** — add `sse-starlette` |
| `frontend/app/hooks/useLivePrices.ts` | **New** — SSE hook |
| `frontend/app/components/WatchlistBar.tsx` | **New** |
| `frontend/app/components/PortfolioStatusBar.tsx` | **New** |
| `frontend/app/page.tsx` | **Modify** — new layout |
| `frontend/app/lib/api.ts` | **Modify** — new LivePrice types |

| File | Action |
|---|---|
| `frontend/app/components/WatchlistWidget.tsx` | **Untouched** (used elsewhere) |
| `frontend/app/components/AgentPortfolioCard.tsx` | **Untouched** (used elsewhere) |

---

## Edge Cases

1. **Boş watchlist:** `"Takip listeniz boş"` mesajı + `/takip` linki
2. **SSE bağlantı kopması:** EventSource auto-reconnect. UI'da eski veri kalır, yeni veri gelene kadar stale gösterilir.
3. **Backend down:** `useLivePrices` error state'e geçer, UI'da `"Canlı fiyat alınamıyor — yeniden bağlanılıyor..."` gösterilir.
4. **Portfolio boş (pozisyon yok):** Sadece nakit gösterilir, pozisyon listesi boş.
5. **Price null:** `"—"` gösterilir, renk nötr.
6. **Hızlı slug değişimi (BIST↔US):** Eski EventSource kapatılır, yenisi açılır. Race condition yok.
7. **Browser tab arka planda:** EventSource throttle olur (browser default), tab öne gelince hemen güncellenir.

---

## Non-Goals (Bu spec'te yok)

- Watchlist ekleme/çıkarma butonu dashboard'da (zaten `/takip` sayfası var)
- Manuel portföy gösterimi (sadece otonom ajan portföyü)
- Fiyat alert/notification
- Grafik/geçmiş fiyat gösterme
- Dark/light tema değişimi (mevcut tema sistemi aynen kullanılır)
