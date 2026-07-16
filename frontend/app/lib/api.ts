export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8012";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

/** Shared headers: API key when configured. */
export function apiHeaders(extra?: Record<string, string>): HeadersInit {
  const h: Record<string, string> = { ...(extra || {}) };
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = {
    ...apiHeaders(),
    ...(init.headers as Record<string, string> | undefined),
  };
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

export type AgentStatus = {
  name: string;
  label: string;
  status: "idle" | "running" | "done" | "error";
  detail: string | null;
  updated_at: string | null;
};

export type PipelineStatus = {
  running: boolean;
  agents: AgentStatus[];
  mode?: string;
  progress?: string[];
  last_error?: string | null;
};

export type StockPick = {
  ticker: string;
  price: number;
  momentum_pct: number;
  fundamental_score: number;
  sentiment_score: number;
  risk_score: number;
  composite_score: number;
  pe_ratio: number | null;
  volatility_annualized: number | null;
  max_drawdown_pct: number | null;
  narrative: string;
};

export type Report = {
  id: number;
  created_at: string;
  summary: string;
  candidates_scanned: number;
  picks: StockPick[];
};

export type ReportListItem = {
  id: number;
  created_at: string;
  candidates_scanned: number;
  top_ticker: string | null;
};

export type WatchlistItem = {
  id: number;
  ticker: string;
  notes: string | null;
  added_at: string;
  price: number | null;
  change_pct: number | null;
};

export type PortfolioPosition = {
  id: number;
  ticker: string;
  quantity: number;
  entry_price: number;
  entry_date: string;
  status: "open" | "closed";
  exit_price: number | null;
  exit_date: string | null;
  notes: string | null;
  current_price: number | null;
  market_value: number | null;
  unrealized_pl: number | null;
  unrealized_pl_pct: number | null;
};

export type PortfolioSummary = {
  positions: PortfolioPosition[];
  total_cost_basis: number;
  total_market_value: number;
  total_pl: number;
  total_pl_pct: number;
};

// ── Autonomous Agent ──

export type AgentPortfolio = {
  portfolio_id?: number;
  portfolio_slug?: string;
  portfolio_name?: string;
  cash: number;
  position_count: number;
  total_cost: number;
  total_market_value: number;
  total_pl: number;
  total_pl_pct: number;
  positions: {
    id: number;
    ticker: string;
    quantity: number;
    entry_price: number;
    current_price: number | null;
    unrealized_pl: number;
  }[];
};

export type AgentDecision = {
  id: number;
  ticker: string;
  action: string;
  quantity: number;
  price: number;
  total_amount: number;
  reasoning: string;
  confidence: number;
  portfolio_id?: number | null;
  created_at: string;
};

// ── Skill (stock_analysis) ──

export type StockAnalysisResult = {
  ticker: string;
  markdown: string;
  conclusion: "strong_buy" | "buy" | "hold" | "sell" | "strong_sell" | "unknown";
  bias_pct: number | null;
  data_missing: string[];
  price_history: Array<{ date: string; open: number; high: number; low: number; close: number; volume: number }>;
  scores: { fundamental?: number | null; sentiment?: number | null; risk?: number | null; composite?: number | null };
  position_pl: { cost_total: number; current_total: number; pl: number; pl_pct: number } | null;
  macro_indicators: Array<{ ticker: string; name: string; label: string; price: number | null; change_pct: number | null; sentiment: "bullish" | "bearish" | "neutral" | null; unit: string }>;
};

export type DividendResult = {
  ticker: string;
  safety_score: number;
  income_rating: "excellent" | "good" | "moderate" | "poor";
  payout_status: "safe" | "moderate" | "high" | "unsustainable" | "unknown";
  payout_ratio: number | null;
  cagr_5y: number | null;
  consecutive_growth_years: number | null;
  dividend_aristocrat: boolean;
  current_yield: number | null;
  data_missing: string[];
};

export type RumorSignal = {
  signal_type: "ma" | "insider" | "analyst" | "regulatory" | "earnings";
  impact_score: number;
  headline: string;
  source: string | null;
  url: string | null;
  timestamp: string | null;
  summary: string | null;
};

export type RumorScanResult = {
  query: string | null;
  signals: RumorSignal[];
  total_impact: number;
};

export type KlineResult = {
  ticker: string;
  chart_png_base64: string | null;
  vlm_analysis: string | null;
  pattern_detected: string | null;
  used_fallback: boolean;
  error: string | null;
};

export type TickerSuggestion = {
  ticker: string;
  name: string;
  exchange: string;
  exchange_name: string;
  type: string;
  sector?: string;
  industry?: string;
};

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.text();
      try {
        const parsed = JSON.parse(body);
        detail = parsed.detail || parsed.message || body;
      } catch {
        detail = body.slice(0, 200);
      }
    } catch {
      detail = res.statusText;
    }
    throw new Error(`API ${res.status}: ${detail || "Bilinmeyen hata"}`);
  }
  return res.json();
}

export const api = {
  getStatus: () => apiFetch("/api/status", { cache: "no-store" }).then(j<PipelineStatus>),
  getLatestReport: () => apiFetch("/api/reports/latest", { cache: "no-store" }).then(j<Report>),
  getHistory: () => apiFetch("/api/reports/history", { cache: "no-store" }).then(j<ReportListItem[]>),
  getReport: (id: number) => apiFetch(`/api/reports/${id}`, { cache: "no-store" }).then(j<Report>),
  generate: (exchange?: string) =>
    apiFetch(`/api/generate${exchange ? `?exchange=${exchange}` : ""}`, { method: "POST" }).then(
      j<{ started: boolean; exchange: string }>
    ),
  deleteReport: (id: number) =>
    apiFetch(`/api/reports/${id}`, { method: "DELETE" })
      .then(j<{ deleted: boolean }>)
      .catch(() => ({ deleted: false })),

  getWatchlist: () => apiFetch("/api/watchlist/personal", { cache: "no-store" }).then(j<WatchlistItem[]>),
  addWatchlistItem: (ticker: string, notes?: string) =>
    apiFetch("/api/watchlist/personal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, notes }),
    }).then(j<WatchlistItem>),
  deleteWatchlistItem: (id: number) =>
    apiFetch(`/api/watchlist/personal/${id}`, { method: "DELETE" }).then(j<{ deleted: boolean }>),

  getPortfolio: () => apiFetch("/api/portfolio", { cache: "no-store" }).then(j<PortfolioSummary>),
  addPortfolioPosition: (payload: {
    ticker: string;
    quantity: number;
    entry_price: number;
    entry_date?: string;
    notes?: string;
  }) =>
    apiFetch("/api/portfolio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(j<PortfolioPosition>),
  closePortfolioPosition: (id: number, exit_price: number) =>
    apiFetch(`/api/portfolio/${id}/close`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exit_price }),
    }).then(j<PortfolioPosition>),
  deletePortfolioPosition: (id: number) =>
    apiFetch(`/api/portfolio/${id}`, { method: "DELETE" }).then(j<{ deleted: boolean }>),

  getAgentPortfolio: (portfolioSlug: string = "bist") =>
    apiFetch(`/api/autonomous/portfolio?portfolio_slug=${portfolioSlug}`).then(j<AgentPortfolio>),
  runAgent: (portfolioSlug: string = "bist") =>
    apiFetch(`/api/autonomous/run?portfolio_slug=${portfolioSlug}`, { method: "POST" }).then(
      j<{ started: boolean; portfolio_slug: string; mode: string }>
    ),
  getAgentDecisions: (portfolioSlug: string = "bist", limit = 20) =>
    apiFetch(`/api/autonomous/decisions?portfolio_slug=${portfolioSlug}&limit=${limit}`).then(
      j<AgentDecision[]>
    ),

  analyzeStock: (
    ticker: string,
    position?: { status: "empty" | "holding"; cost?: number; shares?: number }
  ) =>
    apiFetch("/api/skill/analyze-stock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, position }),
    }).then(j<StockAnalysisResult>),
  analyzeDividend: (ticker: string) =>
    apiFetch("/api/skill/analyze-dividend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    }).then(j<DividendResult>),
  scanRumors: (query?: string) =>
    apiFetch("/api/skill/scan-rumors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    }).then(j<RumorScanResult>),
  analyzeKline: (ticker: string, period = "6mo") =>
    apiFetch("/api/skill/analyze-kline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, period }),
    }).then(j<KlineResult>),

  suggestTickers: (q: string) =>
    apiFetch(`/api/screener/suggest?q=${encodeURIComponent(q)}`, { cache: "no-store" }).then(
      j<TickerSuggestion[]>
    ),

  getScreenerDetail: (ticker: string, period = "5d", interval = "1h") =>
    apiFetch(`/api/screener/${encodeURIComponent(ticker)}?period=${period}&interval=${interval}`, {
      cache: "no-store",
    }).then(j<Record<string, unknown>>),

  analyzeTicker: (ticker: string) =>
    apiFetch(`/api/screener/${encodeURIComponent(ticker)}/analyze`, { method: "POST" }).then(
      j<{ started?: boolean }>
    ),

  createPrediction: (ticker: string) =>
    apiFetch(`/api/predictions/${encodeURIComponent(ticker)}`, { method: "POST" }).then(
      j<Record<string, unknown>>
    ),

  getUnreadCount: () =>
    apiFetch("/api/notifications/unread-count", { cache: "no-store" }).then(j<{ count: number }>),
  markAllNotificationsRead: () =>
    apiFetch("/api/notifications/read-all", { method: "POST" }).then(j<{ ok?: boolean }>),
  markReportNotificationsRead: (id: number) =>
    apiFetch(`/api/notifications/read-by-report/${id}`, { method: "POST" }).then(j<{ ok?: boolean }>),

  // Admin
  listProviders: () => apiFetch("/api/admin/providers").then(j<unknown[]>),
  listModels: (providerId?: number) =>
    apiFetch(`/api/admin/models${providerId != null ? `?provider_id=${providerId}` : ""}`).then(
      j<unknown[]>
    ),
  testModel: (modelId: number) =>
    apiFetch(`/api/admin/models/${modelId}/test`, { method: "POST" }).then(j<Record<string, unknown>>),

  resetPortfolio: (portfolioSlug?: string) =>
    apiFetch(
      `/api/admin/reset/portfolio${portfolioSlug ? `?portfolio_slug=${portfolioSlug}` : ""}`,
      { method: "POST", headers: { "X-Confirm-Reset": "yes" } }
    ).then(
      j<{
        deleted: Record<string, number>;
        balance_cash: number;
        balance_starting: number;
        portfolio_slug?: string;
      }>
    ),
  resetReports: () =>
    apiFetch("/api/admin/reset/reports", {
      method: "POST",
      headers: { "X-Confirm-Reset": "yes" },
    }).then(j<{ deleted: Record<string, number> }>),
  resetAll: (portfolioSlug?: string) =>
    apiFetch(`/api/admin/reset/all${portfolioSlug ? `?portfolio_slug=${portfolioSlug}` : ""}`, {
      method: "POST",
      headers: { "X-Confirm-Reset": "yes" },
    }).then(
      j<{
        portfolio: {
          deleted: Record<string, number>;
          balance_cash: number;
          portfolio_slug?: string;
        };
        reports: { deleted: Record<string, number> };
      }>
    ),
};
