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
  created_at: string;
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

  // ── Autonomous Agent ──
  getAgentPortfolio: () =>
    fetch(`${API_BASE}/api/autonomous/portfolio`).then(j<AgentPortfolio>),
  runAgent: () =>
    fetch(`${API_BASE}/api/autonomous/run`, { method: "POST" }).then(j<{ started: boolean; mode: string }>),
  getAgentDecisions: (limit = 20) =>
    fetch(`${API_BASE}/api/autonomous/decisions?limit=${limit}`).then(j<AgentDecision[]>),
};
