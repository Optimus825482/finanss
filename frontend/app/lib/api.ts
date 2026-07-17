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
  // Faz 1
  fair_value?: number | null;
  margin_pct?: number | null;
  valuation_assessment?: string | null;
  llm_reasoning?: string | null;
  llm_target_price?: number | null;
  llm_expected_return_pct?: number | null;
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
  llm_reasoning?: string | null;
  llm_target_price?: number | null;
  llm_expected_return_pct?: number | null;
  momentum_pct?: number | null;
  // Faz 2
  fair_value?: number | null;
  margin_pct?: number | null;
  valuation_assessment?: string | null;
  fair_value_models?: Array<{ method: string; value: number; inputs?: Record<string, unknown> }>;
  predictions?: Record<string, { predicted: number; drift_pct: number; lower_bound: number; upper_bound: number; signal: number; source: string }> | null;
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

// ── Faz 4: Yeni Skill Results ──

export type SectorRotationResult = {
  query: string | null;
  sector?: string;
  sectors: Array<{ name: string; ticker_count: number; avg_return_pct: number; tickers: string[] }>;
  top_sector: string | null;
  bottom_sector: string | null;
};

export type CorrelationResult = {
  tickers: string[];
  matrix: number[][];
  clusters: string[][];
  highest_correlation: { pair: string[]; value: number } | null;
  lowest_correlation: { pair: string[]; value: number } | null;
  error?: string;
};

export type InsiderResult = {
  ticker: string;
  transactions: Array<{ type: string; shares: number; value: number | null; insider_name: string; date: string }>;
  net_sentiment: "bullish" | "bearish" | "neutral";
  buy_count: number;
  sell_count: number;
  buy_value: number;
  sell_value: number;
  data_missing: string[];
};

export type UnusualOptionsResult = {
  ticker: string;
  options_activity: Array<{ strike: number; expiry: string; volume: number; open_interest: number; type: "call" | "put"; sentiment: "bullish" | "bearish"; last_price: number }>;
  put_call_ratio: number | null;
  unusual_count: number;
  sentiment: "bullish" | "bearish" | "neutral";
  data_missing: string[];
};

export type EarningsSurpriseResult = {
  ticker: string;
  history: Array<{ date: string; estimated: number; actual: number; surprise_pct: number }>;
  avg_surprise_pct: number;
  next_earnings_date: string | null;
  beat_count: number;
  miss_count: number;
  sentiment: "bullish" | "bearish" | "neutral";
  data_missing: string[];
};

export type SeasonalityResult = {
  ticker: string;
  monthly_returns: Record<string, { avg_return_pct: number; win_rate_pct: number; sample_years: number }>;
  quarterly_patterns: Record<string, { avg_return_pct: number; win_rate_pct: number; sample_years: number }>;
  best_month: string | null;
  worst_month: string | null;
  best_quarter: string | null;
  worst_quarter: string | null;
  data_missing: string[];
};

export type FairValueSkillResult = {
  ticker: string;
  fair_value: number | null;
  current_price: number | null;
  margin_pct: number | null;
  assessment: string | null;
  models: Array<{ method: string; value: number; inputs?: Record<string, unknown>; error?: string }>;
  markdown: string;
  data_missing: string[];
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
  getLatestReport: (exchange?: string) =>
    apiFetch(`/api/reports/latest${exchange ? `?exchange=${exchange}` : ""}`, { cache: "no-store" }).then(j<Report>),
  getHistory: (exchange?: string) =>
    apiFetch(`/api/reports/history${exchange ? `?exchange=${exchange}` : ""}`, { cache: "no-store" }).then(j<ReportListItem[]>),
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

  // Faz 3: Deep Batch
  generateDeep: (exchange?: string) =>
    apiFetch(`/api/generate/deep${exchange ? `?exchange=${exchange}` : ""}`, { method: "POST" }).then(
      j<{ started: boolean; exchange: string; mode: string }>
    ),

  // Faz 4: Yeni Skill'ler
  analyzeSectorRotation: (query?: string) =>
    apiFetch("/api/skill/sector-rotation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query || null }),
    }).then(j<SectorRotationResult>),

  analyzeCorrelation: (tickers?: string) =>
    apiFetch("/api/skill/correlation-matrix", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers: tickers || null }),
    }).then(j<CorrelationResult>),

  analyzeInsider: (ticker: string) =>
    apiFetch("/api/skill/insider-activity", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    }).then(j<InsiderResult>),

  analyzeUnusualOptions: (ticker: string) =>
    apiFetch("/api/skill/unusual-options", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    }).then(j<UnusualOptionsResult>),

  analyzeEarningsSurprise: (ticker: string) =>
    apiFetch("/api/skill/earnings-surprise", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    }).then(j<EarningsSurpriseResult>),

  analyzeSeasonality: (ticker: string) =>
    apiFetch("/api/skill/seasonality", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    }).then(j<SeasonalityResult>),

  analyzeFairValue: (ticker: string) =>
    apiFetch("/api/skill/fair-value", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    }).then(j<FairValueSkillResult>),

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
