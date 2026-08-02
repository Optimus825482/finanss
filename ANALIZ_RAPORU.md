# ORBIS FINAI — Mimari & Kod Kalitesi Analiz Raporu

> Tamamlayıcı: ORBIS_AI_AGENT_ANALIZI.md (agent odaklı) · GÜVENLIK_RAPORU.md (11 bulgu, 2 kritik) · TEST_KAPSAM_RAPORU.md (19 dosya) · PERFORMANS_RAPORU.md (14 risk) · VERI_DOGULUK_RAPORU.md (1 tasarım bulgusu) · ONCEKI_OTURUM_BULGULARI.md
> Tarih: 2026-08-02 · Tüm repo tarandı: 90+ dosya, 28 servis, 17 router, 9 agent, 13 skill

---

## 1. Sistem Genel Bakış

**ORBIS Finance Analyze Team** — kurumsal düzey, terminal temalı (amber/black) AI yatırım araştırma platformu.

```
┌─ FRONTEND (Next.js 14, port 3009) ──────────────────────┐
│ Dashboard · Portfoy · Raporlar · Skill · Ayarlar · BIST │
│ 14 komponent · 4 hook · SSE canli fiyat akisi           │
└──────────────┬──────────────────────────────────────────┘
               │ REST (X-API-Key) + SSE (/api/prices/stream)
┌──────────────┴──────────────────────────────────────────┐
│ BACKEND (FastAPI, port 8012)                            │
│                                                          │
│  ORCHESTRATOR (2-stage pipeline + deep)                  │
│    Stage 1: technical prescreen (400+ ticker → ~8)       │
│    Stage 2: Fundamental → Sentiment → Risk → Report      │
│                                                          │
│  AGENTS (9)                                              │
│    Scanner · Fundamental · Sentiment · News · Risk ·     │
│    RiskManager · BullBearResearcher · Report · Autonomous│
│                                                          │
│  SKILLS (13)                                             │
│    stock_analysis · dividend · kline · rumor · watchlist │
│    sector_rotation · correlation · insider · options ·   │
│    earnings_surprise · seasonality · fair_value          │
│    + anti-hallucination SkillRouter (7 onlem)            │
│                                                          │
│  SERVICES (28)                                           │
│    fair_value · prediction(XGBoost) · piotroski ·        │
│    hmm_regime · regime_detector · ic_tracker ·           │
│    cross_sectional · alpha_generator · position_sizing · │
│    portfolio_optimizer(MPT) · memory(pgvector) ·         │
│    llm_bridge(LiteLLM) · web_search · translation ·      │
│    market_data · balance · screener · technicals · ...   │
│                                                          │
│  DB: PostgreSQL 16 + pgvector (6 alembic migration)      │
└──────────────────────────────────────────────────────────┘
```

**Stack:** FastAPI 0.115 · SQLAlchemy 2 · Pydantic v2 · yfinance · LiteLLM · XGBoost · scipy SLSQP · VADER · APScheduler · pgvector · Next.js 14 + lightweight-charts · Docker Compose 3 servis · GitHub Actions CI

---

## 2. Test Sonuçları (Doğrulanmış)

| Ölçüt | Değer |
|-------|-------|
| Toplam test | **211 geçti, 0 fail** (önce: 6 fail + 1 collection error) |
| Coverage | **%22** (7379 stmt) — düşük, kritik modüller %0 |
| Lint (düzeltilen 4 dosya) | ruff temiz |
| CI | backend: ruff + pytest · frontend: lint + jest + build |

### Bu analizde bulunup düzeltilen buglar (commit 7247b60)

| # | Bug | Dosya | Etki | Düzeltme |
|---|-----|-------|------|----------|
| 1 | `dedup_signals` içinde `now_istanbul` import edilmemiş → NameError | `app/skills/rumor_scanner.py:76` | Rumor scan skill + 3 test kırılıyordu | import eklendi |
| 2 | `np.cumsum(Series)` → `series[-1]` label-based **KeyError: -1** | `app/services/alpha_generator.py:58` | `detect_volume_anomaly` her çağrıda exception → `smart_money_signal: "error"`. Üretimde de kırılırdı | `np.asarray` ile düzeltildi |
| 3 | `_parse_reddit_json` fonksiyonu yok ama test import ediyor → collection error | `app/services/web_search.py` + `tests/test_web_search.py:4` | Tüm test suite'i çalışmıyordu | Parser geri eklendi (403 bot block notu korundu) |
| 4 | `SPOT` (NASDAQ+NYSE) ve `WBD` (NASDAQ+NYSE) mükerrer | `app/config.py:62,92` | Universe dup + config test fail | NYSE kayıtları kaldırıldı |
| 5 | `alpha_generator.py` F401 (unused Optional) + E401 (json,re tek satır) | `app/services/alpha_generator.py:12,136` | Lint fail | Temizlendi |

---

## 3. Mimari Değerlendirme

### 3.1 Güçlü Yönler (9.0/10 altyapı)

1. **yfinance dayanıklılık katmanı** — `yf_utils.py` exponential backoff + retry + stderr susturma; her çağrı noktası `safe_*` wrapper kullanıyor
2. **NaN/Inf savunması** — `sanitize.py` `_native()` ile np.float64→float dönüşümü (SQLAlchemy "schema np does not exist" hatasını önler), `sanitize_dict` recursive, tüm pipeline'da guard
3. **LLM fallback zinciri** — 6 provider (DB→Ollama→Groq→Gemini→OpenAI→Claude), vision/embedding ayrı fallback, tüm LLM çağrıları best-effort (exception sessiz yutulur, şablon devreye girer)
4. **SkillRouter anti-hallucination** — 7 katmanlı savunma: örnek JSON yok, pydantic strict, whitelist, retry+feedback, max_turns, handler kısıtı, audit log
5. **Çoklu portföy** — BIST/US ayrı cash + universe + pozisyon limiti, `ensure_portfolio` runtime guarantee
6. **Risk yönetimi derinliği** — Kelly fractional sizing, MPT optimizer, HMM regime, IC tracking, RiskManager veto — hepsi otonom ajan kararında zincirlenmiş
7. **RD-Agent/Qlib ilhamı** — factor_extractor, dual momentum, rolling eğitim, feedback loop gerçekten uygulanmış
8. **Migrasyon disiplini** — `init_db()` yalnızca pgvector extension; şema tamamen alembic; `create_all` yok
9. **BIST ticker özel yolu** — `.IS` için batch download çalışmadığından individual + Semaphore(8) concurrent

### 3.2 Mimari Borçlar (öncelikli)

| # | Borç | Dosya | Etki | Öneri |
|---|------|-------|------|-------|
| M1 | **Orchestrator singleton** | `orchestrator.py:181` `orchestrator = Orchestrator()` | Concurrent pipeline çalıştırılamaz; 2 portföy aynı anda rapor isterse 409 | `run_pipeline`'ı instance-agnostic yap veya per-exchange orchestrator havuzu |
| M2 | **autonomous_agent.py 1005 satır monolit** | `services/autonomous_agent.py` | 8 sorumluluk tek sınıfta (trading, LLM, candidates, pending, cleanup, kelly...) | Ara katman: `TradingExecutor`, `CandidateGatherer`, `DecisionEngine` |
| M3 | **Scheduler thread'lerde `asyncio.run` + `create_task` loop çakışması** | `scheduler.py:19,28,41` + `autonomous_agent.py:978,377` | **Kritik**: `_gather_candidates:377` `asyncio.create_task(orchestrator.run_pipeline())` kendi loop'una schedule edilir; `asyncio.run` bitince loop kapanır → pipeline task'ı **"Task was destroyed but it is pending" ile sessizce ölür**, rapor üretimi tetiklenmez. Ayrıca `is_running` thread-safe değil (race) | `run_coroutine_threadsafe` veya lifespan'da tek kalıcı async loop; `is_running`'e Lock (PERFORMANS_RAPORU R7.1) |
| M4 | **LLM JSON parse tek nokta** | `report_agent.py:230` `json.loads(raw)` | LLM bozuk JSON dönerse tüm pick enrichment sessiz düşer (skill_router json_repair kullanıyor, burada kullanılmıyor) | `_parse_json_robust`'u paylaş |
| M5 | **`test_web_search` collection error'ı CI'yi kırıyordu** | `tests/test_web_search.py` | CI `pytest` tüm suite'te fail — uzun süredir görünmemiş | Düzeltildi; CI'ya `--ignore` yerine tam suite girmeli |
| M6 | **NewsAnalyst main pipeline'da değil** | `orchestrator.py` + `screener_service.py` | SentimentAgent (VADER-only) kullanılıyor, NewsAnalyst (burst+trend+event) boşa duruyor | ORBIS_AI_AGENT_ANALIZI zayıflık #1 — Stage 2'ye NewsAnalyst ekle |
| M7 | **Coverage %22, kritik modüller %0** | tüm routers, orchestrator, autonomous_agent, balance_service | Para işlemleri + veto + pipeline test edilmiyor | TEST_KAPSAM_RAPORU'ndaki top-10 listesi |
| M8 | **`get_live_prices` .IS per-ticker sleep 0.15s** | `market_data.py:96` | 20 BIST ticker = ~3s seri; SSE her 3sn'de çağırıyor | Ticker.info yerine batch (son commit'te kısmen yapıldı); paralel fetch |
| M9 | **Backend SSE endpoint'i var ama frontend polling yapıyor** | `backend/app/routers/prices.py:97` (SSE `/api/prices/stream`) vs `frontend/app/hooks/useLivePrices.ts:12` | Backend SSE altyapısı boşa yazılmış; frontend 3s'de REST polling (`/watchlist/personal` + `/autonomous/portfolio`) — 2x rate-limit yükü, SSE'nin verimliliği kayıp | `useLivePrices`'ı `EventSource('/api/prices/stream')` ile değiştir |
| M10 | **XGBoost her `create_prediction`'da 24 model fit, `n_jobs=-1`** | `prediction_engine.py:505-511,552-563` | Kullanıcı 8 hisse analiz ederse 24 XGBoost fit, tüm CPU çekirdekleri doyar → diğer istekler starvation. Model cache yok (disk dosyası var ama `_has_model` kontrolü train'de kullanılmıyor) | `_has_model` + mtime<24h ise train'i atla → 30-90s → <1s (PERFORMANS_RAPORU R5.1, hızlı kazanım #1) |
| M11 | **LLM gather iki kez (mükerrer token maliyeti)** | `report_agent.py:290` + `orchestrator.py:226` | `_compose_async` zaten `_llm_enrich_pick` gather yapıyor, `_run_deep` bütün picks'i bir kez daha zenginleştiriyor → 8 pick × 2 LLM çağrısı aynı promptla | `_run_deep`'teki tekrar gather'ı kaldır (R2.2) |
| M12 | **Naive/aware datetime karşılaştırması** | `autonomous_agent.py:357` | `datetime.now()` (naive) vs `Report.created_at = now_istanbul()` (UTC+3 aware) → `TypeError: can't subtract offset-naive and offset-aware` ile tur patlayabilir veya yanlış rapor yaşı | `astimezone` normalize (R3.1, hızlı kazanım #3) |
| M13 | **Dual momentum + volume anomaly tur başına ~80 yfinance çağrısı (0.3s sleep'ler)** | `autonomous_agent.py:477,496` + `cross_sectional.py:112-126` | 8 aday × (9+1) çağrı + 4.8s saf sleep her 30dk'da, her portföyde; sektör döngüsü N aday × sektör boyutu yeniden indiriyor | TTL cache (6saat) + `asyncio.gather` paralel + tek 6mo download paylaşımı (R1.4, hızlı kazanım #4) |

---

## 4. Agent Mimarisi Detayı

### 4.1 Skor Zinciri

```
FundamentalAgent: PE(10-25→90p) + Growth(>20%→95p) + ROE(>20%→90p) + Debt(<50→85p) / 4
                   + Piotroski F≥7 +5 / F≤3 -5
SentimentAgent:  VADER compound avg → (avg+1)*50, veri yoksa 50 nötr
RiskAgent:       vol_ann × 0.45 + |max_dd| × 0.35 + beta × 0.20  (yüksek = riskli)
Composite:       fundamental × 0.40 + sentiment × 0.30 + (100-risk) × 0.30
ReportAgent:     composite + fair_value + makro + LLM enrichment (pick başına hedef fiyat)
```

### 4.2 Otonom Ajan Karar Akışı (30dk, 2 portföy)

```
think_and_act
 ├─ HMM regime güncelle (günlük)
 ├─ IC tracking (geçmiş trade'lerden)
 ├─ Piyasa açık mı?
 │   ├─ AÇIK → pending order'ları gerçekleştir → stuck cleanup → _llm_decide
 │   │        (LLM yoksa rule-based: RSI>75 sat, skor≥60 al, Kelly+RiskManager+MPT bütçe)
 │   └─ KAPALI → _deep_analyze_and_queue (top 5 aday, stock_analysis skill, PendingOrder)
 └─ Her karar trading_decisions'a loglanır
```

### 4.3 Skill Sistemi (13 tool)

Router: LLM → fenced JSON → pydantic strict validate → whitelist → handler (DB/okuma) → audit.
`_rules.py` Python-zorunlu behavior: bias>%5 → buy engellenir (LLM'e bırakılmaz).

---

## 5. Kod Kalitesi Örnekleri

### İyi (taklit edilecek)
```python
# orchestrator.py:112 — NaN/Inf guard DB öncesi
pick = sanitize_dict(pick)
db.add(StockPick(... composite_score=sanitize_float(pick["composite_score"], 50.0) ...))

# yf_utils.py — stderr susturma + backoff
with contextlib.redirect_stderr(io.StringIO()):
    return with_retry(yf.download, *args, retries=retries, **kwargs)

# memory_service.py — embedding optional, memory yine de kaydedilir
vector = await get_embedding(embed_text)
if vector is not None: ...
```

### Kötü (düzeltilecek)
```python
# report_agent.py:230 — LLM JSON raw parse, fallback yok (M4)
parsed = _json.loads(raw)   # JSONDecodeError → pick enrichment kayıp

# scheduler.py — thread + asyncio.run karışımı (M3)
def _run_pipeline_sync():
    asyncio.run(orchestrator.run_pipeline())  # uvicorn loop'tan bağımsız

# autonomous_agent.py:978 — sync wrapper her çağrıda yeni loop
return asyncio.run(self.think_and_act(db, exchanges))
```

---

## 6. Bağımlılık & Yapılandırma

- **requirements.txt**: 27 paket — `scipy` ve `matplotlib` yüklü ama sadece optimizer/kline'da; ağırdır, opsiyonel yapılabilir
- **DATABASE_URL zorunlu** (`config.py:40` raise) — doğru, SQLite geçişini engeller
- **CI: sqlite:///ci-test.db** kullanıyor ama pgvector import'u model'de → SQLite'ta `Vector` tipi çalışmaz mı? Testler çalıştı çünkü memory model import edilmiyor (lazy). Risk: CI gerçek DB'yi test etmiyor
- **Docker**: pgvector:pg16 + healthcheck + migration retry (10 deneme) + non-root appuser — sağlam
- **`.env.example`** eksiksiz; `ALLOW_DESTRUCTIVE_RESET` guard'ı var ama `middleware.py`'de bu env kullanılmıyor (her zaman X-Confirm-Reset ister — güvenli taraf, ama env ölü kod)

---

## 7. Güvenlik Ön Bulguları (detay GÜVENLIK_RAPORU.md)

- **Yüksek**: `FERNET_KEY` yoksa LLM API key düz metin DB'de (`llm.py` — decode fallback)
- **Orta**: API_KEY boşsa auth tamamen kapalı (`.env.example` "local dev only" notu var ama docker prod'da boş kalabilir)
- **Orta**: `ticker` path parametreleri doğrudan yfinance'a gidiyor (injection değil ama beklenmedik input → uzun süreli network call)
- **Düşük**: CORS allowlist sabit 2 origin; slowapi 120/min tüm API'de

---

## 8. Öncelikli Aksiyon Listesi

| Öncelik | Aksiyon | Referans |
|---------|---------|----------|
| 🔴 P1 | NewsAnalyst + BullBearResearcher Stage 2'ye ekle (skor kalitesi) | ORBIS_AI_AGENT_ANALIZI #1, M6 |
| 🔴 P1 | Scheduler'ı tek kalıcı async loop'a taşı (create_task sessiz ölümü) | M3, R7.1 |
| 🔴 P1 | **XGBoost günlük train gate (24 fit/CPU starvation)** | M10, R5.1 |
| 🔴 P1 | **FERNET_KEY zorunlu; API_KEY boşsa prod fail** | GÜVENLIK_RAPORU S1/S4 |
| 🟠 P2 | Peter Lynch docstring/PEG netliği (temettü dahil PEG yorumu) | VERI_DOGULUK_RAPORU Bölüm 1 |
| 🟠 P2 | LLM JSON parse'ı skill_router'ın robust parse'ıyla birleştir | M4 |
| 🟠 P2 | Para işlemleri testi: execute_buy/sell, balance, veto (coverage %22) | TEST_KAPSAM_RAPORU |
| 🟠 P2 | autonomous_agent.py 1005 satırı böl | M2 |
| 🟡 P3 | SSRF doğrulaması (provider test base_url) | GÜVENLIK_RAPORU S3 |
| 🟡 P3 | CI'ya gerçek PostgreSQL + pgvector service ekle | Bölüm 6 |
| 🟢 P4 | Orchestrator singleton'ı kaldır · SSE frontend'e bağla (M9) · fair_value safe_ticker_info | M1/M9, VERI_DOGULUK Bölüm 11 |
