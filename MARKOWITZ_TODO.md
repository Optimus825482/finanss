# Markowitz MPT — Portföy Optimizasyonu Yapılacaklar

ROADMAP Aşama 4.1: `backend/app/services/portfolio_optimizer.py` planlı, henüz yok. Bu dosya, mevcut otonom portföy yönetimi (`autonomous_agent.py`) sabit %25 position sizing yerine Markowitz mean-variance + Sharpe optimum ağırlık dağıtımı kullanacak şekilde entegre olacak.

## Hedef
- Otonom ajan buy kararlarında her hisseye sabit %25 yerine **optimum portföy ağırlığı** uygula.
- Sharpe ratio maksimize eden, korelasyon bilinçli ağırlık dağıtımı.
- Risk-adjusted getiri ölçümü (Sharpe, Sortino).

## Mimari

```
backend/app/
├── services/
│   ├── portfolio_optimizer.py    # NEW — Markowitz mean-variance optimizasyon
│   └── autonomous_agent.py        # EXTEND — _rule_based_decide/_llm_decide_with_llm qty hesabını optimize_Weights'ten al
├── routers/
│   └── portfolio.py               # EXTEND — /api/portfolio/optimize endpoint
└── tests/
    ├── test_portfolio_optimizer.py  # NEW — pure matematik testleri
    └── test_correlation_matrix.py    # NEW — korelasyon hesabı
```

## Bağımlılıklar

`requirements.txt`'e ekle:
- `scipy>=1.11.0` — `scipy.optimize.minimize` (SLSQP ile constrained MPT)
- `numpy` (zaten var) — kovaryans matrisi

`cvxpy` alternatif (daha temiz constrained QP) ama scipy yeterli ve daha az bağımlılık.

## Modül Tasarımı — `portfolio_optimizer.py`

### Pure fonksiyonlar (test edilebilir, config/DB bağımsız)

```python
def covariance_matrix(returns: np.ndarray) -> np.ndarray:
    """Günlük getiri matrisi → kovaryans matrisi (yıllıklaştırılmış)."""

def correlation_matrix(returns: np.ndarray) -> np.ndarray:
    """Korelasyon matrisi — çeşitlendirme analizi için."""

def portfolio_return(weights: np.ndarray, mean_returns: np.ndarray) -> float:
    """w · mean_returns → beklenen getiri."""

def portfolio_volatility(weights: np.ndarray, cov_matrix: np.ndarray) -> float:
    """sqrt(wᵀ · Σ · w) → portföy volatilitesi."""

def sharpe_ratio(weights, mean_returns, cov_matrix, risk_free_rate=0.02) -> float:
    """(return - rf) / volatility → Sharpe."""

def optimize_weights(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.02,
    max_weight: float = 0.25,        # tek hissede max %25 (mevcut kural)
    min_weight: float = 0.0,          # short yok
    target_return: Optional[float] = None,  # None → max Sharpe
) -> np.ndarray:
    """SLSQP ile Sharpe maksimize eden ağırlık vektörü.

    Kısıtlar:
    - sum(weights) = 1
    - 0 <= weight_i <= max_weight
    - (opsiyonel) target_return >= belirli seviye

    Returns: optimum weights array (sum = 1)
    """

def min_variance_weights(mean_returns, cov_matrix, max_weight=0.25) -> np.ndarray:
    """Min varyans portföyü — risk-altın yaklaşım, getiri hedefi yok."""

def efficient_frontier(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.02,
    n_points: int = 50,
    max_weight: float = 0.25,
) -> list[dict]:
    """Efficient frontier üzerinde N nokta — her biri {return, vol, sharpe, weights}.
    Frontend dashboard için (şimdilik opsiyonel)."""
```

### Async run wrapper (DB/veri çeker)

```python
async def optimize_for_tickers(
    tickers: list[str],
    period: str = "2y",
    risk_free_rate: float = 0.02,
    max_weight: float = 0.25,
) -> dict:
    """Ticker listesi → optimum ağırlık dağıtımı.

    1. Her ticker için safe_ticker_history (period) → günlük getiri series
    2. Getiri matrisi oluştur (pandas DataFrame → numpy)
    3. mean_returns (yıllıklaştırılmış: × 252)
    4. cov_matrix (yıllıklaştırılmış: × 252)
    5. optimize_weights → optimum weights
    6. Sharpe, vol, beklenen getiri hesapla

    Returns: {
        "tickers": [...],
        "weights": {ticker: weight},  # 0 altında None (hariç tutulur)
        "expected_return": float,
        "volatility": float,
        "sharpe": float,
        "correlation": [[...]],         # heatmap için (opsiyonel)
        "data_missing": [tickers without enough history],
    }
    """
```

## Entegrasyon — `autonomous_agent.py`

### Mevcut durum (kaldırılacak):
```python
# _rule_based_decide satır ~393
qty = max(1, int(max_per_pos / c["price"])) if c["price"] > 0 else 0
# max_per_pos = cash * 0.25  # SABİT %25
```

### Yeni:
```python
# Karar öncesi: adaylar için optimum ağırlık hesapla (cache'li, günde 1 kez)
from app.services.portfolio_optimizer import optimize_for_tickers

if not hasattr(self, "_weights_cache") or stale:
    candidates_tickers = [c["ticker"] for c in candidates[:10]]
    opt = await optimize_for_tickers(candidates_tickers)
    self._weights_cache = opt["weights"]

# Her adayın alımı için o ticker'ın optimum ağırlığını kullan
weight = self._weights_cache.get(c["ticker"], 0)
max_per_pos = cash * weight  # sabit %25 yerine optimize weight
qty = max(1, int(max_per_pos / c["price"])) if c["price"] > 0 and weight > 0 else 0
```

### LLM prompt genişletme:
`_llm_decide_with_llm` prompt'una "optimum ağırlıklar" bilgisini ekle:
```
=== PORTFÖY OPTİMİZASYONU (Markowitz) ===
Adaylar için optimum ağırlıklar (Sharpe maksimize):
  AAPL: %18 (korelasyon 0.42)
  MSFT: %22 (korelasyon 0.38)
  ...
LLM bu ağırlıkları aşmamalı (max_weight=%25).
```

## API — `routers/portfolio.py`

Yeni endpoint ekle:
```python
@router.post("/optimize")
async def optimize_portfolio(
    tickers: list[str] = Body(...),
    period: str = "2y",
    db: Session = Depends(get_db),
):
    """Markowitz optimizasyonu — optimum ağırlık dağıtımı."""
    from app.services.portfolio_optimizer import optimize_for_tickers
    return await optimize_for_tickers(tickers, period=period)
```

## Frontend — `SkillPanel.tsx` genişletme (opsiyonel)

5. tab olarak "⚖️ Optimize" ekle:
- Ticker listesi input (çoklu, virgülle)
- `/api/portfolio/optimize` çağır
- Sonuç: ağırlık dağılımı bar chart + Sharpe/vol/metrikler
- Korelasyon heatmap (opsiyonel, `react-plotly` veya `recharts` gerek)

## Testler — `test_portfolio_optimizer.py`

Pure matematik testleri (config/DB bağımsız):
- `covariance_matrix` — doğru simetrik matris, pozitif semi-definit
- `correlation_matrix` — köşegen 1.0, simetrik
- `portfolio_return` — `w·μ` doğru
- `portfolio_volatility` — `sqrt(wᵀΣw)` doğru
- `sharpe_ratio` — `(r-rf)/σ` formülü
- `optimize_weights`:
  - sum(weights) ≈ 1 (tolerans 1e-6)
  - 0 <= weight_i <= max_weight
  - Sharpe daha yüksek tek-asset'ten daha iyi (diversification)
- `min_variance_weights` — vol daha düşük tek-asset'ten
- Edge case: tek ticker → weight=1.0 (max_weight kısıtı ihmal edilemez ama 1 ticker'da mecbur)
- Edge case: yüksek korelasyonlu ticker'lar → ağırlıklar daha eşit (diversification az)

`test_correlation_matrix.py`:
- 2 ticker, korelasyon 1.0 (mükemmel pozitif) → diversification yok
- 2 ticker, korelasyon -1.0 → mükemmel hedge
- NaN handling (eksik veri)

## Fazlama

1. **Veri toplama**: `safe_ticker_history` her ticker için 2y OHLCV → günlük getiri series. 10 ticker × 2y = ~500 gün × 10 = 5000 veri noktası. Hızlı.
2. **Kovaryans hesabı**: `np.cov(returns.T)` — tek satır, çok hızlı.
3. **Optimizasyon**: `scipy.optimize.minimize` SLSQP — 10 değişken, ~1 saniye.
4. **Cache**: günlük 1 kez yeter (piyasa kapanışında). `autonomous_agent` `__init__`'te cache timestamp kontrolü.
5. **Risk-free rate**: `0.02` (2% yıllık) sabit — config'e taşı (`RISK_FREE_RATE`).

## Atlanan / Gelecek

- **Black-Litterman**: piyasa görüşü + yatırımcı görüşü birleştirme. Markowitz'in aşırı duyarlılığını azaltır. İleri aşama.
- **Risk parity**: volatiliteye göre eşit risk katkısı. Markowitz alternatifi.
- **Rebalancing threshold**: ağırlıklar %5'ten fazla saparsa rebalance. Mevcut `_rule_based_decide` içinde uygulanabilir.
- **Backtest**: optimize edilmiş ağırlıkların geçmiş performansı. `backtesting-frameworks` skill mevcut.
- **Sector constraint**: `optimize_weights`'a sektör bazlı max kısıtı (örn tek sektör max %40). `sector_map` dict gerek.

## Estimate
- Kod: ~250-300 satır `portfolio_optimizer.py` + 150-200 satır test.
- Süre: 2-3 saat (scipy öğrenme/curves dahil).
- Risk: scipy SLSQP convergence başarısız olursa fallback (min_variance_weights) gerek.

## Bağlantılar
- ROADMAP: `docs/ROADMAP.md` Aşama 4.1
- Mevcut position sizing: `autonomous_agent.py:393` (`max_per_pos = cash * 0.25`)
- Korelasyon verisi: `safe_ticker_history` (yf_utils.py)
- Backtest skill: `C:\Users\erkan\.zcode\skills\backtesting-frameworks\SKILL.md`
