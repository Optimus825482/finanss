# ORBIS FINAI — Düzeltme ve Geliştirme Planı

Kullanıcı seçimleri: **Tüm kapsamı düzelt** (kritik+yüksek+orta), **XGBoost ekle**, **legacy modu kaldır**.

6 faz. Her faz bağımsız çalıştırılabilir, sıralı git commit'lenebilir.

---

## FAZ 1 — Güvenlik & İnfra Sertleştirme

### 1.1. Hardcoded şifre (C1, M3)
**`docker-compose.yaml`**
- `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-518518Erkan}` → default'u kaldır, `${POSTGRES_PASSWORD:?POSTGRES_PASSWORD gerekli}` (boşsa container başlamaz)
- `DATABASE_URL` default'tan aynı şifreyi çekmeye devam etsin ama default hardcoded kalmasın
- Frontend build arg `NEXT_PUBLIC_API_URL` default'u `http://localhost:8012` yapılsın, production'da env ile override edilsin (şimdiki `https://finans.erkanerdem.online` hardcoded kalmasın)

### 1.2. Entrypoint fail-fast
**`backend/docker-entrypoint.sh`**
- 10 deneme后 alembic fail ederse `exit 1` ekle (şu an başarısız olsa bile uvicorn başlıyor)
- Loop sonrası kontrol: `if [ $SUCCESS -ne 1 ]; then exit 1; fi`

### 1.3. APIKeyMiddleware sertleştir
**`backend/app/middleware.py`**
- Plain `!=` → `secrets.compare_digest` (constant-time karşılaştırma)
- `API_KEY = os.getenv(...)` import-time → her istekte `os.getenv` oku (env değişince reload gerekmesin; düşük maliyet)

### 1.4. init_db + Alembic çakışmasını çöz (H3)
**`backend/app/database.py`**
- `init_db()` sadece `CREATE EXTENSION IF NOT EXISTS vector` yapsın
- `Base.metadata.create_all` çağrısını kaldır — şema yönetimi tamamen Alembic'e devredilsin
- `docker-entrypoint.sh` zaten `alembic upgrade head` çalıştırıyor → tek doğruluk kaynağı

**`backend/alembic/versions/52c8062ed019_initial_baseline.py`**
- Mevcut baseline `create_all` kullanıyor — bu idempotent ama ALTER detected etmiyor. Yorum satırına not düş: "sonraki model değişiklikleri için `alembic revision --autogenerate` üret"
- Şimdilik baseline'i koru (çalışıyor), ama yeni migration'lar gerçek `op.add_column` vb. kullansın

---

## FAZ 2 — Backend Çekirdek Temizliği

### 2.1. trading_decisions raw SQL → model (C2)
**`backend/app/services/autonomous_agent.py`**
- `_log_decision` (L155-171): `sa.MetaData().reflect()` + `td_table.insert()` → `TradingDecision` modeli ile `db.add(TradingDecision(...))`
- `models/core.py`'de `TradingDecision` zaten tanımlı (L106) — kullan

### 2.2. Router'ları Depends(get_db)'ye taşı (C3)
9 router'da `SessionLocal()` direkt kullanımı → `db: Session = Depends(get_db)` parametresi:

| Router | SessionLocal noktaları |
|--------|----------------------|
| `reports.py` | L34, L51, L76, L93 |
| `watchlist.py` | L19, L37, L59 |
| `portfolio.py` | L37, L65, L97, L120 |
| `profile.py` | L12, L22 |
| `chat.py` | L19, L92, L100 |
| `memory.py` | L24, L37, L48, L57 |
| `admin.py` | L20, L29, L42, L54, L73, L82, L98, L110, L123, L132, L143, L163 |
| `screener_analyze.py` | L27, L60 |
| `autonomous.py` | L13, L23 |

- Her route'ta `try/finally db.close()` bloklarını kaldır (get_db yield auto-close ediyor)
- `# TODO: use Depends(get_db)` yorumlarını kaldır
- `balance.py`, `notifications.py`, `predictions.py` zaten temiz — dokunma

### 2.3. asyncio deprecation (H1)
**`backend/app/services/autonomous_agent.py`** `run()` (L468)
- `asyncio.get_event_loop()` → `asyncio.run(self.think_and_act(db, exchanges))`
- **`backend/app/scheduler.py`** `_run_pipeline_sync` ve `_run_autonomous_agent_sync`
- `ThreadPoolExecutor` + `asyncio.run` → `asyncio.run(orchestrator.run_pipeline())` (thread pool gereksiz, asyncio.run kendi loop yaratır)

### 2.4. FastAPI lifespan (M4)
**`backend/app/main.py`**
- `@app.on_event("startup")` → `@asynccontextmanager async def lifespan(app)` context manager
- `app = FastAPI(title=..., lifespan=lifespan)`

### 2.5. Legacy modu kaldır (M2, M5)
**Sil:**
- `backend/app/agents/scanner_agent.py` → tamamen sil
- `config.py` → `WATCHLIST`, `SCANNER_MIN_MOMENTUM_PCT`, `SCANNER_LOOKBACK_DAYS` sil
- `orchestrator.py` → `mode` field, `_run_legacy`, `ScannerAgent` import + self.scanner kaldır
  - `run_pipeline()` her zaman two-stage çalışsın (exchanges gerekli olsun, boşsa tüm evren)
  - `_run_two_stage`'in `self.scanner._set(...)` referanslarını `progress_log` veya fundamental agent'a taşı
- `main.py`/router'larda `from app.agents.scanner_agent import ScannerAgent` import'u varsa kaldır

### 2.6. Duplicate ticker'ları temizle (M6)
**`config.py`** `STOCK_UNIVERSE`
- NYSE içinde tekrar: NFLX (L41), PEP (L34/L41), REGN, VRTX, GILD, AMGN, BIIB (sağlık listesinde), ORLY (L40/L41)
- BIST içinde: PGSUS (L57/L72)
- `list(dict.fromkeys(...))` ile zaten dedup var ama listeyi elle temizle (okunabilirlik)

### 2.7. Router hata yönetimi düzeltmeleri (ek)
- **`chat.py`**: `generate()` çağrısını try/except sar, LLM hatasında 500 yerine anlamlı mesaj
- **`memory.py`**: `json.loads(data_snapshot)` try/except sar
- **`admin.py`**: `body: dict` → Pydantic schema'lar (`ProviderCreate`, `ModelCreate` vb.) — en azından `body["name"]` KeyError'ı düzelt
- **`screener.py`**: bare `except: return []` → `logger.warning` ekle
- **`screener_analyze.py`/`screener_screen.py`**: BG task'lara try/except + logging ekle
- **`autonomous.py`**: `agent.run(exchanges)` sync çağrı `async def _run` içinde → `await asyncio.to_thread(agent.run, exchanges)` ile bloklamayı önle

---

## FAZ 3 — yfinance Rate-Limit Koruması (M1)

**Yeni dosya: `backend/app/services/yf_utils.py`**
```python
import asyncio, functools, logging
import yfinance as yf

logger = logging.getLogger(__name__)

def with_retry(fn, *args, retries=3, backoff=1.5, **kwargs):
    """yfinance çağrısı için exponential backoff + retry."""
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == retries - 1: raise
            wait = backoff ** attempt
            logger.warning("yfinance retry %d/%d: %s", attempt+1, retries, e)
            import time; time.sleep(wait)
    return None
```

**Uygula (çağrı noktaları):**
- `market_data.py` `get_live_prices` → `yf.download` retry ile sar
- `screener_service.py` `stage1_prescreen` batch download + `_prescreen_individual` `_fetch`
- `fundamental_agent.py` `yf.Ticker().info`
- `sentiment_agent.py` `yf.Ticker().news`
- `risk_agent.py` benchmark download
- `autonomous_agent.py` `analyze_single`
- `prediction_engine.py` `_evaluate_one`

---

## FAZ 4 — XGBoost Tahmin Motoru (H5)

### 4.1. Bağımlılık
**`backend/requirements.txt`** → `xgboost>=2.0.0` ekle

### 4.2. Model refactor
**`backend/app/services/prediction_engine.py`**
- `EnsemblePredictor` → `XGBoostPredictor` olarak yükselt
- Model kayıt/yükleme: `backend/data/models/{ticker}_xgb.json` (XGBoost native save)
- İlk çağrıda: AlphaEngine ile feature çıkar → model yoksa heuristic ağırlıklarla başlat + eğitim verisi topla
- Walk-forward: son 60 günlük fiyat + feature'lar ile eğit, 7/15/30g tahmin üret
- Eğitim verisi yeterli (<30 sample) değilse heuristic fallback (şimdiki BASE_WEIGHTS)

### 4.3. Öğrenme döngüsü
- `evaluate_due_predictions` → hatalı tahminleri model eğitimine feedback olarak besle
- Basit: her değerlendirme sonrası o ticker'ın modelini son verilerle yeniden eğit
- Model drift için: 30 günde bir otomatik yeniden eğitim (scheduler'a eklenebilir — şimdilik manual)

---

## FAZ 5 — Frontend Hata Yönetimi (H4)

### 5.1. Toast/error sistemi
**Yeni: `frontend/app/components/ErrorBoundary.tsx`**
- React error boundary wrapper, yakalanmayan render hatalarını göster

**`frontend/app/lib/api.ts`**
- `j()` helper → response body'yi parse etmeden önce `res.text()` oku, hata mesajını çıkar
- Her `catch` → kullanıcıya gösterilecek hata mesajı döndür

**`frontend/app/page.tsx`** (ve diğer sayfalar)
- `console.warn` ile yutulan hatalar → `setError()` state'e yaz, UI'da göster
- Toast component veya mevcut error banner'ı genişlet

### 5.2. Loading/error state'leri
- `AgentPortfolioCard`, `WatchlistWidget`, `StockCard` → loading/error/empty state'leri tutarlı yap

---

## FAZ 6 — Test Altyapısı (H2)

### 6.1. Backend test'ler
**`backend/pytest.ini`**
- `asyncio_mode = auto` ekle
- `addopts = --cov=app --cov-report=term-missing` ekle (coverage)

**Yeni test dosyaları:**
- `backend/tests/test_screener_service.py` — `get_universe`, `stage1_prescreen` mock'lu test
- `backend/tests/test_agents.py` — `FundamentalAgent._score_*`, `RiskAgent` hesaplamaları
- `backend/tests/test_prediction_engine.py` — `AlphaEngine.price_features` dummy veri ile, `EnsemblePredictor.predict`
- `backend/tests/test_autonomous_agent.py` — `_rule_based_decide` mock portföy ile
- `backend/tests/test_api.py` — FastAPI `TestClient` ile `/api/status`, `/api/reports` smoke test'ler

### 6.2. Frontend test'ler
**`frontend/jest.config.js`** — `moduleNameMapper` ekle (path alias, CSS mock)
**Yeni:**
- `frontend/tests/api.test.ts` — `api` fonksiyonların mock fetch ile
- `frontend/tests/StockCard.test.tsx` — render test

### 6.3. CI güncelle
**`.github/workflows/ci.yml`**
- Backend job'a `pip install -r requirements.txt pytest pytest-asyncio pytest-cov httpx` ekle
- `pytest --asyncio-mode=auto` adımı ekle
- Frontend job'a `npm test` ekle

---

## Dosya Değişiklik Özeti

| Faz | Değişen Dosyalar | Yeni Dosyalar |
|-----|-----------------|---------------|
| 1 | docker-compose.yaml, docker-entrypoint.sh, middleware.py, database.py | — |
| 2 | autonomous_agent.py, orchestrator.py, config.py, main.py, 9 router, chat/memory/admin/screener_*.py | — (scanner_agent.py silinir) |
| 3 | market_data.py, screener_service.py, fundamental/sentiment/risk_agent.py, prediction_engine.py | yf_utils.py |
| 4 | prediction_engine.py, requirements.txt | data/models/ (model kayıtları) |
| 5 | api.ts, page.tsx, StockCard/WatchlistWidget/AgentPortfolioCard | ErrorBoundary.tsx |
| 6 | pytest.ini, ci.yml, jest.config.js | 6 test dosyası |

Toplam: ~35 dosya değişir, ~10 yeni dosya, 1 dosya silinir.

## Commit Stratejisi
Her faz ayrı commit: `fix(security): ...`, `refactor(backend): ...`, `feat(retry): ...`, `feat(ml): xgboost predictor`, `feat(frontend): error handling`, `test: real test suite + CI`. Faz sırasıyla ilerle, her fazın sonunda lint + test koş.