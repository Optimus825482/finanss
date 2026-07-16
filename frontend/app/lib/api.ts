const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8012";

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

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    // Backend'ten detay mesajını çıkarmaya çalış
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
  getStatus: () => fetch(`${API_BASE}/api/status`, { cache: "no-store" }).then(j<PipelineStatus>),
  getLatestReport: () => fetch(`${API_BASE}/api/reports/latest`, { cache: "no-store" }).then(j<Report>),
  getHistory: () => fetch(`${API_BASE}/api/reports/history`, { cache: "no-store" }).then(j<ReportListItem[]>),
  getReport: (id: number) => fetch(`${API_BASE}/api/reports/${id}`, { cache: "no-store" }).then(j<Report>),
  generate: (exchange?: string) => fetch(`${API_BASE}/api/generate${exchange ? `?exchange=${exchange}` : ""}`, { method: "POST" }).then(j<{ started: boolean; exchange: string }>),
  deleteReport: (id: number) => fetch(`${API_BASE}/api/reports/${id}`, { method: "DELETE" }).then(j<{ deleted: boolean }>).catch(() => ({ deleted: false })),

  getWatchlist: () =>
    fetch(`${API_BASE}/api/watchlist/personal`, { cache: "no-store" }).then(j<WatchlistItem[]>),
  addWatchlistItem: (ticker: string, notes?: string) =>
    fetch(`${API_BASE}/api/watchlist/personal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, notes }),
    }).then(j<WatchlistItem>),
  deleteWatchlistItem: (id: number) =>
    fetch(`${API_BASE}/api/watchlist/personal/${id}`, { method: "DELETE" }).then(j<{ deleted: boolean }>),

  getPortfolio: () => fetch(`${API_BASE}/api/portfolio`, { cache: "no-store" }).then(j<PortfolioSummary>),
  addPortfolioPosition: (payload: {
    ticker: string;
    quantity: number;
    entry_price: number;
    entry_date?: string;
    notes?: string;
  }) =>
    fetch(`${API_BASE}/api/portfolio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(j<PortfolioPosition>),
  closePortfolioPosition: (id: number, exit_price: number) =>
    fetch(`${API_BASE}/api/portfolio/${id}/close`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exit_price }),
    }).then(j<PortfolioPosition>),
  deletePortfolioPosition: (id: number) =>
    fetch(`${API_BASE}/api/portfolio/${id}`, { method: "DELETE" }).then(j<{ deleted: boolean }>),

  // ── Autonomous Agent (portföy-bilinçli) ──
  getAgentPortfolio: (portfolioSlug: string = "bist") =>
    fetch(`${API_BASE}/api/autonomous/portfolio?portfolio_slug=${portfolioSlug}`).then(j<AgentPortfolio>),
  runAgent: (portfolioSlug: string = "bist") =>
    fetch(`${API_BASE}/api/autonomous/run?portfolio_slug=${portfolioSlug}`, { method: "POST" }).then(j<{ started: boolean; portfolio_slug: string; mode: string }>),
  getAgentDecisions: (portfolioSlug: string = "bist", limit = 20) =>
    fetch(`${API_BASE}/api/autonomous/decisions?portfolio_slug=${portfolioSlug}&limit=${limit}`).then(j<AgentDecision[]>),

  // ── Skill (stock_analysis entegrasyonu) ──
  analyzeStock: (ticker: string, position?: { status: "empty" | "holding"; cost?: number; shares?: number }) =>
    fetch(`${API_BASE}/api/skill/analyze-stock`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, position }),
    }).then(j<StockAnalysisResult>),
  analyzeDividend: (ticker: string) =>
    fetch(`${API_BASE}/api/skill/analyze-dividend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    }).then(j<DividendResult>),
  scanRumors: (query?: string) =>
    fetch(`${API_BASE}/api/skill/scan-rumors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    }).then(j<RumorScanResult>),
  analyzeKline: (ticker: string, period = "6mo") =>
    fetch(`${API_BASE}/api/skill/analyze-kline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, period }),
    }).then(j<KlineResult>),

  // ── Sembol arama (Yahoo Finance autocomplete) ──
  suggestTickers: (q: string) =>
    fetch(`${API_BASE}/api/screener/suggest?q=${encodeURIComponent(q)}`, { cache: "no-store" })
      .then(j<Array<{ ticker: string; name: string; exchange: string; exchange_name: string; type: string; sector?: string; industry?: string }>>),

  // ── Sistem Sıfırlama (admin) — portföy-bilinçli ──
  resetPortfolio: (portfolioSlug?: string) =>
    fetch(`${API_BASE}/api/admin/reset/portfolio${portfolioSlug ? `?portfolio_slug=${portfolioSlug}` : ""}`, { method: "POST" })
      .then(j<{ deleted: Record<string, number>; balance_cash: number; balance_starting: number; portfolio_slug?: string }>()),
  resetReports: () =>
    fetch(`${API_BASE}/api/admin/reset/reports`, { method: "POST" })
      .then(j<{ deleted: Record<string, number> }>),
  resetAll: (portfolioSlug?: string) =>
    fetch(`${API_BASE}/api/admin/reset/all${portfolioSlug ? `?portfolio_slug=${portfolioSlug}` : ""}`, { method: "POST" })
      .then(j<{ portfolio: { deleted: Record<string, number>; balance_cash: number; portfolio_slug?: string }; reports: { deleted: Record<string, number> } }>),
};
