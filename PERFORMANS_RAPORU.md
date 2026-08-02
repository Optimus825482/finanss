# ORBIS FINAI — Backend Performans Risk Analizi

Tarih: 2026-08-02
Kapsam: `backend/` — yfinance çağrı yüzeyi, agent pipeline, otonom ajan, DB, prediction engine, SSE stream, scheduler/orchestrator.
Metod: satır-satır statik inceleme (dosya:satır referanslarıyla). Etki: Yüksek / Orta / Düşük.

---

## 1. yfinance Çağrı Yüzeyi

### R1.1 `with_retry` tamamen senkron + process-bloklayıcı — YÜKSEK
`app/services/yf_utils.py:21-44`

- `time.sleep(wait)` retry backoff'u event loop thread'ini bloklar. Async context'te hiçbir çağrı `asyncio.to_thread` sarmalı içinde retry yapmıyor (sarmalayanlar `safe_download`/`safe_ticker_*` çağrılarının *dışında*).
- `screener_service.py:269` `_prescreen_individual._fetch` → `to_thread(safe_download)` → retry sleep'ler sadece o worker thread'ini bloklar (kabul edilebilir).
- Asıl risk: `fundamental_agent.py:78`, `risk_agent.py:32`, `fair_value.py:136`, `autonomous_agent.py` `analyze_single`'daki `safe_ticker_info/history` çağrıları. `fundamental_agent.run` `asyncio.to_thread(self._analyze, candidates)` ile sarmalanıyor — o yüzden retry sleep'i worker thread'de kalır. Ancak **sıralı tekil döngülerde** (örn. `_gather_candidates` içindeki `compute_dual_momentum` → `safe_ticker_history` x ~9) retry patlaması wall-clock süresini katlar: her başarısız ticker için 1.5s + 2.25s + 3.375s ≈ 7s.
- Ayrıca `safe_*` wrapper'ları her çağrıda `import yfinance as yf` (lazım) yapıyor; yfinance ilk import'u ağır (1-3s) ve her worker thread ilk çağrıda öder.
- İyileştirme: (a) `with_retry`'e `jitter` ekle (rate-limit çakışmalarını azaltır); (b) `safe_*` fonksiyonlarında modül-seviyesinde tek `import yfinance` (lazy global), çağrı başına import maliyetini kaldır; (c) `yf.Ticker` nesnesini reuse et — her çağrıda yeni Ticker kurulumu yerine ticker bazlı LRU cache (örn. `functools.lru_cache` ile `_get_ticker`), yfinance Ticker init + curl session kurulumu ucuz değil.

### R1.2 `safe_download` batch + `.IS` ayrıştırması — ORTA
`app/services/yf_utils.py:45-55`, `app/services/market_data.py:63-93`

- `get_live_prices` non-BIST'leri tek `yf.download(list)` ile çekiyor — doğru. Ama BIST ticker'ları **teker teker** `safe_download([t])` ile, aralarında `_t.sleep(0.15)` (market_data.py:88) — N BIST ticker = N ayrı HTTP çağrısı + N*0.15s.
- `get_live_prices` cache yazımı yalnızca `price` veya `change_pct` doluysa (`market_data.py:135`); `None` sonuçlar cache'lenmez → her 3s polling'de aynı başarısız ticker'lar yeniden çekilir (bkz. R6.1).
- İyileştirme: (a) BIST için de batch `yf.download` denemesi yap, başarısız olursa bireysel fallback (yfinance 0.2.x `.IS` batch'i artık kısmen destekliyor); (b) `None` sonuçları 10-15s TTL ile cache'le (negatif cache); (c) BIST sleep'i düşür (0.05s) veya Semaphore ile sınırlandır.

### R1.3 screener stage1: batch vs bireysel — YÜKSEK (BIST evreni için)
`app/services/screener_service.py:76-89` (batch), `:270-285` (`_prescreen_individual`)

- BIST evreni ~130 ticker (`config.py` BIST bloğu). `stage1_prescreen` herhangi bir `.IS` görünce **tüm listeyi** `_prescreen_individual`'e sokar → 130 ayrı `safe_download` + Semaphore(8). Sem=8 ile bile 130 çağrı ~130 × (0.5-2s) / 8 ≈ **30-60 sn** sürer. Her çağrı 3 retry hakkı taşır.
- Ayrıca `_prescreen_individual` ve batch path'te `_score_hist` (RSI/momentum/vol hesapları) iki kez kopyalanmış durumda (`_score_hist` `screener_service.py:206-356` içinde gömülü) — bakım riski.
- İyileştirme: (a) `.IS` ticker'lar için batch denemesini de yap (yukarıdaki gibi); (b) Semaphore'u 8→16 çıkar (yfinance 5s rate limit'e takılmadan); (c) aynı gün içinde stage1 tekrar çalışıyorsa sonucu DB'ye cache'le (report/stockpick'lerden bağımsız kısa TTL in-memory); (d) `_score_hist`'i ortak fonksiyona çıkar (duplication).

### R1.4 `cross_sectional.py` + `alpha_generator.py` 0.3s sleep'ler — YÜKSEK
`app/services/autonomous_agent.py:477` (`_time.sleep(0.3)`), `:496` (`_time2.sleep(0.3)`)

- `_gather_candidates`'ta her aday için `compute_dual_momentum` (≈9 `safe_ticker_history` çağrısı: kendi + sektör x8) + `detect_volume_anomaly` (1 çağrı). Sıralı `for` döngüsü + her adayda 0.3s×2 sleep.
- 8 aday = 8 × (9+1) = **80 yfinance çağrısı + 4.8s saf sleep** her 30dk tur başına (her portföy için). Üstelik `compute_cross_sectional_momentum` içindeki sektör döngüsü `sector_tickers[:8]`'i **sıralı** çekiyor (`cross_sectional.py:112-126`).
- `alpha_generator.detect_volume_anomaly` ayrıca `period="2mo"` çekiyor — önceki `compute_time_series_momentum`'un `6mo` verisiyle çakışıyor, iki kez download ediliyor.
- İyileştirme: (a) dual momentum'u `asyncio.gather` + `to_thread` ile paralelleştir (adaylar arası ve sektör içi); (b) `cross_sectional`'a in-memory TTL cache ekle (aynı sektör ticker'ları tek turda tek sefer çekilir — `compute_dual_momentum`'un her aday çağrısı sektörün tamamını yeniden indiriyor, **N aday × sektör boyutu** çağrı); (c) sleep'leri kaldırıp Semaphore(8) ile sınırla; (d) tek `6mo` history download'ını paylaş (anomaly `2mo` alt kümesini kullansın).

---

## 2. Sıralı Agent Pipeline — `orchestrator.py` stage2_deep_analysis

### R2.1 Ajan zinciri tamamen sıralı — YÜKSEK
`app/services/screener_service.py:150-168` (`stage2_deep_analysis`), çağıran `app/orchestrator.py:107-120` (`_run_two_stage`) ve `:196-201` (`_run_deep`)

```
fundamental.run → sentiment.run → risk.run
```
her biri `asyncio.to_thread` ile tek thread; ajanlar **birbirini beklemeden** paralel çalışabilir çünkü bağımsızlar (`fundamental` safe_ticker_info, `sentiment` safe_ticker_news, `risk` history hesaplama). Sıralı toplam = 3 × (en yavaş ajan wall-time) yerine ~1× en yavaş.
- Veri akışı gereksinimi yok: `fundamental`/`sentiment`/`risk` hepsi `history` + kendi çağrılarını kullanır, ortak değişken yok.

### R2.2 Deep pipeline'da fair_value + prediction + LLM — KISMEN concurrent — ORTA
`app/orchestrator.py:206-236`

- **Fair Value: concurrent** — `_asyncio.gather(*[_deep_enrich(c)])` ✓ (`:210-220`).
- **Prediction (create_prediction / XGBoost train): yok**. `_run_deep`'te prediction çağrısı yok; prediction yalnızca `skills/stock_analysis.py:442` `_ok` içinde ve `predictions.py:64` router'ında çağrılıyor. `create_prediction` içinde `XGBoostPredictor.train` **senkron** ve `n_jobs=-1` (tüm CPU) — tek pick başına 30-90s sürebilir (aşağıda R5).
- **LLM: concurrent** — `_llm_enrich_pick` `asyncio.gather` ✓ (`:226-232`), ama `report_agent._compose_async`'te **iki kez** gather: biri `_compose_async` içinde (`report_agent.py:290`), biri `_run_deep`'te (`orchestrator.py:226`) → 8 pick için LLM çağrıları iki kez, aynı promptla (mükerrer token maliyeti, ~2× LLM latency).
- İyileştirme: (a) stage2 ajanlarını `asyncio.gather` ile paralel çalıştır; (b) `_run_deep`'teki tekrar LLM gather'ını kaldır (zaten `_compose_async` yapıyor); (c) prediction'ı deep pipeline'a eklersen `asyncio.to_thread` ile sar ve model eğitimini cache'le (R5).

---

## 3. `autonomous_agent.py` — 30dk tur, rapor tetikleme + 90s bekleme

### R3.1 90s senkron bekleme döngüsü — YÜKSEK
`app/services/autonomous_agent.py:375-395` (`_gather_candidates`)

- Rapor eskiyse/yoksa `asyncio.create_task(orchestrator.run_pipeline(...))` ile pipeline'ı **yanlış event loop'a** gönderiyor (aşağıda R7.2) ve sonra `for attempt in range(30): await asyncio.sleep(3)` ile 90s boyunca DB'yi pollluyor.
- Sonuç: 30dk'lık turda **en az 90s boşta** kalma; eğer pipeline da tetiklenemezse (loop çakışması) 90s sonunda screener'a düşer → 130 ticker stage1 (~30-60s) + 8 × analyze_single (her biri ~10-20s) → tek tur **5-10 dk** sürebilir.
- `_gather_candidates` `db2 = SessionLocal()` her 3s'te yeni session açıyor — 30 döngü = 30 session (kısa ömürlü, düşük ama gereksiz yük).
- Ayrıca rapor tazelik kontrolü `datetime.now()` (naive UTC) vs `Report.created_at = now_istanbul()` (UTC+3 aware) — **naive/aware karşılaştırması** (`:357`). Postgres `DateTime` naive olarak döner, `now_istanbul()` ise aware → `age.total_seconds()` `TypeError: can't subtract offset-naive and offset-aware` ile patlayabilir veya yanlış yaş hesaplayabilir. Yüksek önemli bug.
- İyileştirme: (a) `created_at`'i `astimezone` ile normalize et; (b) pipeline'ı çağıran `asyncio.create_task` yerine `orchestrator.run_pipeline`'ı kendi event loop'unda (R7.2) çalıştır; (c) 90s polllama yerine tek query + 10-15s ara; (d) bekleme döngüsünde `latest2.id != latest.id` kontrolü yeterli, her döngüde `joinedload` gerekmiyor — `Report.picks` lazy yükle.

### R3.2 Her turda tam yfinance yüzeyi — YÜKSEK
`autonomous_agent.py` `think_and_act` (sayfa 1) → `get_portfolio` (`get_live_prices` pozisyonlar) + `_gather_candidates` (rapor DB'den geldiyse sadece 80 yfinance çağrısı; gelmediyse screener + analyze_single). Her 30dk'da **2 portföy** = BIST (~130 ticker bireysel) + US (~130 batch). Günlük: 48 tur × 2 portföy.

- Rapor DB'den geldiğinde bile `_gather_candidates` dual momentum + volume anomaly 80 çağrı/tur (R1.4). Yani "sadece 8 aday" görünümüne rağmen her turda ~80-160 yfinance çağrısı.
- İyileştirme: (a) dual momentum/volume anomaly sonuçlarını `ticker → {sonuç, ts}` TTL cache (örn. 6 saat) ile cache'le — fiyat verisi gün içi değişse de momentum sinyali 30dk'da nadiren anlamlı değişir; (b) R1.4'teki gibi tek history download'ını paylaş.

### R3.3 `_rule_based_decide` içinde canlı yfinance RSI — ORTA
`autonomous_agent.py:700-717` (`_get_rsi`)

- LLM yoksa her pozisyon + aday için `yf.Ticker(ticker).history(period="1mo")` **doğrudan** (safe wrapper olmadan, retry yok). `_rsi_cache` per-call (her `run()` içinde sıfırlanır) — tur başına sadece 1 kez ama wrapper'sız + sıralı.
- İyileştirme: `safe_ticker_history` kullan; `_rsi_cache`'i sınıf seviyesine taşı (TTL'li).

---

## 4. DB — SQLAlchemy Session & N+1

### R4.1 `pool_size=10 / max_overflow=20` — ORTA
`app/database.py:7`

- Toplam 30 bağlantı tavanı. Eşzamanlı yük: SSE stream (her client ayrı session) + 2 otonom ajan (aynı anda `SessionLocal` + 30×3s poll session'ları) + pipeline `_persist` + LLM `_get_db_credentials` (her LLM çağrısında `llm_bridge.py:75-191` yeni session!). `_get_db_credentials` her `generate()`'de 1+ DB session açıyor — `_run_deep`'te 8 pick × LLM + summary = ~10 LLM çağrısı = ~10-20 session.
- `get_live_prices` makro (`get_macro_indicators`) + `predictions.py` router + watchlist yazma... 30'luk havuz kritik anlarda tükenir → `TimeoutError: connection pool timeout`. Pool tükenmesi SSE'yi (her 3s'de session açan) direkt etkiler.
- Ayrıca sync `create_engine` — async FastAPI'de tüm DB erişimi thread'de yürüyor ama yine de bloklayıcı.
- İyileştirme: (a) `pool_size=20, max_overflow=40` (veya `pool_pre_ping` zaten var); (b) `_get_db_credentials`'a 5-10sn TTL cache; (c) SSE `_fetch_prices_sync` içindeki `get_portfolio` (query + `get_live_prices`) ve watchlist query'sini tek session'da birleştir (zaten öyle — iyi).

### R4.2 N+1: `get_portfolio` → `get_live_prices` her pozisyonda — DÜŞÜK-ORTA
`autonomous_agent.py:133-138` (`get_portfolio`)

- Pozisyonlar için tek `get_live_prices(tickers)` çağrısı var (batch) — N+1 değil ✓. Ama `_execute_pending_orders`'ta her bekleyen emir için `get_live_prices([order.ticker])` ayrı çağrı (`:490`) — emir başına 1 çağrı, N emir = N çağrı. Küçük ölçekte düşük.

### R4.3 `joinedload` ile tek rapor — DÜŞÜK
`autonomous_agent.py:355, 383` — `joinedload(Report.picks)` doğru kullanılmış. `_persist` (orchestrator.py:249-287) her pick için ayrı `StockPick` insert — N insert tek transaction, kabul edilebilir.

---

## 5. `prediction_engine.py` — XGBoost

### R5.1 Eğitim sıklığı: her `create_prediction` çağrısında — YÜKSEK
`app/services/prediction_engine.py:505-511`

```python
trained = XGBoostPredictor.train(ticker.upper(), closes, highs, lows, volumes, opens)
```

- **Her prediction oluşturmada full yeniden eğitim**: 3 horizon × `XGBRegressor(n_estimators=100, n_jobs=-1)`. `n_jobs=-1` = tüm CPU çekirdekleri. Eğitim süresi ticker başına ~15-60s (feature engineering `price_features` 100 bar × 60+ factor Python döngüsü + model fit).
- `create_prediction` `stock_analysis.py:442` ve `predictions.py:64`'ten çağrılıyor. Kullanıcı 8 hisse analiz etse → 8 × 3 model = **24 XGBoost fit**, her biri tüm çekirdekleri doyar. Diğer istekler (SSE, diğer ajanlar) CPU starvation yaşar.
- Model cache: **yok**. Sadece disk dosyası (`data/models/{ticker}_xgb_{horizon}.json`) var ve `predict` sırasında yeniden yükleniyor (`_xgb_predict` model load her çağrıda) — ama **eğitim her seferinde tekrarlanıyor**, cache kullanılmıyor.
- İyileştirme: (a) eğitimi günlük + ticker başına yap: `_model_path` mtime'ı 24 saatten eskiyse eğit, yoksa mevcut modelle predict (`_has_model` zaten var — `create_prediction`'da `_has_model` kontrolüyle train'i atla); (b) `_xgb_predict`'e process/thread-level model cache (functools.lru_cache ile `load_model`); (c) `n_jobs`'u `max(1, cpu//2)` yap; (d) `_evaluate_one`'daki retrain (`:552-563`) de aynı günlük gate'e tabi olsun.

---

## 6. SSE `prices/stream`

### R6.1 3s polling × cache etkileşimi — ORTA
`app/routers/prices.py:70-88`

- `_fetch_prices_sync` her 3s'te: watchlist query + `get_live_prices(wl_tickers)` + `AutonomousAgent(...).get_portfolio(db)` (yine `get_live_prices`). Cache TTL 60s → **20 polling turundan 1'i** gerçekten yfinance çağırır. Doğru tasarım ✓.
- Ama (a) `get_portfolio` içindeki `get_live_prices` ayrı çağrı — watchlist ve portfolio aynı ticker'ı içeriyorsa aynı `_price_cache`'ten okur ✓ (paylaşılan modül seviyesi cache). (b) BIST ticker'lar her cache-miss'te `safe_download([t])` tekil → watchlist 20 BIST ticker = 20 çağrı her 60s'de bir.
- (c) `get_live_prices` cache yazımı `None`'ları cache'lemiyor (R1.2) → başarısız ticker 20 polling turunda **20 kez** yeniden denenir.
- (d) `AutonomousAgent(portfolio_slug=...)` her 3s'te **yeniden instantiate** ediliyor (`prices.py:58`) — `__init__` `PORTFOLIOS` lookup + display name; hafif ama gereksiz. `_portfolio_id` lazy olduğundan `ensure_portfolio` her 3s'te DB'ye yazma denemesi yapabilir (`get_portfolio` → `_ensure_portfolio_id` → `ensure_portfolio` query+insert if missing).
- İyileştirme: (a) ajan'ı modül seviyesinde singleton cache'le (veya `get_portfolio`'ya `agent=None` parametresi); (b) `None` fiyatları negatif cache; (c) stream'i tek `get_live_prices(combined_tickers)` ile besle, portfolio/wl ayrımını client'ta yap.

---

## 7. Orchestrator Singleton + Scheduler Thread'lerde asyncio.run

### R7.1 `asyncio.run` + `asyncio.create_task` loop çakışması — YÜKSEK
`app/scheduler.py:19` (`_run_pipeline_sync`), `:28/41` (`_run_autonomous_*`), `autonomous_agent.py:978` (`run`), `autonomous_agent.py:377` (`asyncio.create_task`)

- APScheduler `BackgroundScheduler` thread'lerinde `asyncio.run(...)` her job'da **yeni event loop** kurar — doğru izolasyon, ama:
  - `_gather_candidates:377` `asyncio.create_task(orchestrator.run_pipeline(...))` **kendi loop'unda** çalışan görevi o loop'a değil... burada hata: `create_task` içinde bulunduğu loop'u kullanır, `think_and_act` `agent.run()` içindeki `asyncio.run` loop'unda çalışıyor → pipeline task'ı o loop'a schedule edilir; `think_and_act` bitince `asyncio.run` loop'u kapatır → **pipeline task'ı "Task was destroyed but it is pending" ile sessizce ölür**. Rapor üretimi tetiklenmez, 90s boşa bekleme + screener fallback yaşanır.
  - `is_running` bayrağı thread-safe değil: `orchestrator.is_running = True` pipeline ortasında; aynı anda scheduler'ın `_run_autonomous_bist_sync` + manuel API tetiklemesi (`routers/autonomous.py` `schedule_agent`) race → iki pipeline aynı anda.
- `asyncio.run` içinde `orchestrator.run_pipeline` `stage1_prescreen`'in `asyncio.gather`'ı (BIST) bu loop'ta çalışır — OK. Ama `to_thread` worker'ları `create_task`/gather ile karışınca `RuntimeError: no running event loop` riski düşük (hep to_thread).
- İyileştirme: (a) scheduler'a **tek kalıcı event loop**: `BackgroundScheduler` yerine `asyncio` background task (lifespan'da `asyncio.create_task(agent_loop())`), `run_pipeline`'ı doğrudan `await`; (b) veya `run_coroutine_threadsafe` ile ana loop'a gönder; (c) `is_running`'i `threading.Lock` + flag ile koru; (d) `_gather_candidates`'taki `create_task`'ı kaldır — `run_pipeline`'ı kendi loop'unda doğrudan çalıştır (bu metod zaten `async`).

### R7.2 Orchestrator singleton'da state yarışı — ORTA
`app/orchestrator.py:27-37` (`__init__`), `_run_two_stage`/`_run_deep`

- Singleton `orchestrator` tek `is_running` flag + `progress_log` listesi paylaşır. `status_snapshot` API'den okunurken pipeline yazarken race → progress log bozulabilir (list append thread-safe ama okuma anlık görüntü değil).
- `self.exchanges` her `run_pipeline` başında overwrite — aynı anda iki farklı exchange çağrısı birbirinin state'ini ezer.
- İyileştirme: (a) exchange'i instance state yerine parametreyle taşı (zaten `_run_two_stage(exchanges)` — `self.exchanges = exchanges` satırını kaldır, `status_snapshot`'ta exchange yerine son çalışan exchange'i ayrı field'da tut); (b) `progress_log` için lock veya son snapshot copy.

---

## En İyi 5 Hızlı Kazanım

1. **XGBoost eğitimini günlük gate'e bağla** (`prediction_engine.py:505`): `_has_model(ticker, h)` + model dosyası mtime < 24h ise `train`'i atla. Etki: `create_prediction` 30-90s → <1s; CPU starvation (24 CPU fit) tamamen kalkar. Tek satırlık `if not all(cls._has_model(t, h) for h in cls.HORIZONS): train(...)`.

2. **stage2 ajanlarını `asyncio.gather` ile paralelleştir** (`screener_service.py:150-168`): fundamental/sentiment/risk bağımsız. Etki: deep analysis süresi ~3× → ~1× (tek en yavaş ajan). 3 satır değişiklik.

3. **`_gather_candidates`'ta naive/aware datetime bug'ını düzelt + 90s poll'u kısalt** (`autonomous_agent.py:357`): `created_at.astimezone(...)` veya `datetime.now(timezone.utc)` kullan; poll aralığını 3s→10s, max 30→9 deneme. Etki: her 30dk turunda 90s boş bekleme → ~0-30s; TypeError ile tur patlaması riski biter.

4. **Dual momentum + volume anomaly'yı TTL cache'le** (`autonomous_agent.py:477,496`): `ticker → {dual, va, ts}` 6 saatlik dict. Etki: tur başına ~80 yfinance çağrısı → ~8 (yalnızca yeni adaylar); rate-limit riski + sleep'ler düşer.

5. **BIST stage1'de `.IS` bireysel indirme öncesi batch denemesi + Semaphore 8→16** (`screener_service.py:270`): etki: 130 ticker tarama 30-60s → 15-30s; ayrıca `None` fiyatları negatif cache'le (`market_data.py:135`) → SSE stream'de başarısız ticker'lar 20 polling turu boyunca tekrar denenmez.

---

## Ek Notlar (düşük öncelik)

- `llm_bridge.generate`'da timeout/retry yok (`llm_bridge.py:147` `await litellm.acompletion`) — LLM provider yavaşsa pipeline asılı kalır. 30-60s timeout + 1 retry ekle.
- `_deep_analyze_and_queue` (`autonomous_agent.py:589`) her aday için `_stock_skill.run` = full skill pipeline (LLM + FV + prediction eğitimi) **sıralı** 5 aday — R5 çözülmeden bu da CPU yoğun.
- `fair_value.py:136` `yf.Ticker(ticker).info` `safe_ticker_info` değil — wrapper'sız, retry'sız. `calculate_fair_value`'yu `safe_ticker_info` ile başlat.
- `stage1` RSI/vol hesapları her adayda numpy yeniden hesaplanıyor; `_score_hist` vs batch path'te mantık ikizlenmiş (`screener_service.py`).
- `get_live_prices` makro göstergeler (`get_macro_indicators`) her rapor üretiminde 8 batch ticker çekiyor — aynı `_price_cache`'ten geçer, cache TTL 60s yeterli.
