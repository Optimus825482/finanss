# ORBIS FINAI Backend — Test Kapsamı Raporu

**Tarih:** 2026-08-02  
**Kapsam:** `D:\DYADAPPS\stock-agent-team\backend`  
**Durum:** 211 test geçiyor, 0 fail — **coverage %22** (7379 stmt, 5764 miss)

---

## 1. Özet

| Metrik | Değer |
|---|---|
| Toplam test | 211 (18 dosya) |
| Geçen / Başarısız | 211 / 0 |
| Coverage (stmt) | **%22** |
| Toplam ifade | 7379 |
| Kaçırılan ifade | 5764 |
| `pytest.ini` kapsamı | `--cov=app` (tüm app paketi) |

**Temel bulgu:** Testler neredeyse yalnızca **saf hesaplama fonksiyonlarına** odaklanmış. Para hareketi yapan, DB yazan, LLM çağıran, HTTP uçlarına sahip tüm kritik modüller (orchestrator, autonomous_agent, risk_manager, balance_service, market_data, research_team, tüm router'lar, stock_analysis) **%0 kapsamda**. "211 test geçiyor" gerçek davranış güvencesi değil, aritmetik yardımcı fonksiyon güvencesidir.

---

## 2. 19 Test Dosyasının Kapsam Analizi

> `tests/` altında 18 dosya var (kullanıcı notunda 19 deniyor; `test_placeholder.py` boş assert içerir ve sayımı şişirir). Her dosyanın neyi test ettiği ve neyi **kaçırdığı**:

| Dosya | Satır | Test | Ne test ediyor | Kritik kaçırdıkları |
|---|---|---|---|---|
| `test_agents.py` | 57 | 19 | `_score_pe/growth/roe/debt`, `_narrative_for`, `_build_rich_summary` | FundamentalAgent/SentimentAgent/RiskAgent/ReportAgent **run()** akışı, NewsAnalyst, BaseAgent |
| `test_alpha_generator.py` | 61 | 7 | `detect_volume_anomaly` mock'lu | `generate_alpha`, LLM alpha üretimi, anomaly → trading kararı entegrasyonu |
| `test_backtest.py` | 19 | 3 | `run_buy_hold`, `run_signal_backtest` (3 happy path) | Edge: boş/short dizi, NaN guard, `max_dd` negatif doğrulaması, tüm `run_backtest` orchestration |
| `test_config.py` | 42 | 11 | Evren tanımı, ağırlık toplamı, zamanlama | `PORTFOLIOS` config (autonomous_agent kullanır), API key kontrolleri, env override |
| `test_cross_sectional.py` | 120 | 16 | `get_sector`, cross/TS/dual momentum mock'lu | Sektör bazlı momentumda `safe_ticker_history` exception yolu, `sector_rank` uç değerler |
| `test_hmm_regime.py` | 68 | 11 | `_gaussian_pdf`, HMM rejim geçişi | `update_hmm_from_market` (canlı veri), `get_adaptive_weights` bear'da risk ağırlığı artışı **doğrulaması** (sadece toplam=1 kontrol ediyor) |
| `test_ic_tracker.py` | 89 | 9 | IC hesaplama, factor weight | `track_signals_from_trades` (DB), IC → scoring ağırlık entegrasyonu |
| `test_placeholder.py` | 3 | 1 | `assert True` | — (silinebilir) |
| `test_portfolio_optimizer.py` | 45 | 3 | `optimize_weights`, `allocate_buy_budgets` | Kısıt ihlali (max_weight), singüler cov, `min_weight>0` |
| `test_prediction_engine.py` | 65 | 10 | feature extraction, heuristic predictor | **XGBoost gerçek model yükleme/çağırma** (sadece `_has_model` false), `create_prediction` (DB yazma) |
| `test_screener_service.py` | 40 | 10 | `get_universe`, `list_exchanges` | **`stage1_prescreen` + `stage2_deep_analysis`** — orchestrator'ın kalbi, %0 kapsam |
| `test_skill_router.py` | 204 | 28 | JSON parse, whitelist, retry, max_turns, audit log | Tool handler exception yolu, `db` bağımlı handler, gerçek skill handler enjeksiyonu |
| `test_skills_dividend.py` | 127 | 25 | payout/cagr/safety/income hesapları | **`run()`** (yfinance+DB entegrasyonu), yıl aralığı uç durumları |
| `test_skills_kline.py` | 52 | 15 | `detect_pattern` mum formasyonları | `analyze_kline` (çizim+rapor), pattern→trading sinyali |
| `test_skills_rumor.py` | 75 | 15 | `impact_for_type`, `_fingerprint`, `dedup_signals` | **`scan` + fetch** (canlı ağ), rumor→alpha skoru |
| `test_stock_analysis.py` | 74 | 28 | `_rules.py` saf kurallar (bias, conclusion, ma, pl) | **`stock_analysis.run()`** — 453 satır, %0. Bias rule LLM'e bırakılmadığının entegrasyon testi yok |
| `test_web_search.py` | 176 | 23 | Parser'lar (DDG/News/Reddit/HN), dedup | **`search_*` ağ çağrıları, retry, hata toleransı, to_rumor akışı** |
| `test_yf_utils.py` | 32 | 8 | `with_retry`, saf wrapper'lar | `safe_ticker_history` (kısmi veri), gerçek MultiIndex yfinance yanıtı, `get_stock_info` |

**Ortak eksen (tüm dosyalar):** DB işlemleri yok (conftest bile yok), HTTP uç testi yok, LLM mock entegrasyonu yalnızca `test_skill_router`'da var.

---

## 3. Kritik Boşluklar (%0 Kapsam Modüller)

| Modül | Satır | Risk | Neden kritik |
|---|---|---|---|
| `app/orchestrator.py` | 287 | **KRİTİK** | Tüm iki-aşamalı pipeline + `_persist` DB yazımı. Stage 1/2, rapor kaydı, webhook. Hata yolu: `run_pipeline` zaten çalışıyor → RuntimeError |
| `app/services/autonomous_agent.py` | 1005 | **KRİTİK** | Para işlemleri: `execute_buy/sell`, yetersiz bakiye guard, pozisyon sahiplik kontrolü, `_cleanup_stuck_positions` (breakeven kapatma), pending order'lar, `_rule_based_decide`, `_llm_decide` fallback, `get_portfolio` hesap doğruluğu |
| `app/agents/risk_manager.py` | 211 | **KRİTİK** | Veto mantığı: `evaluate` → vol/sector/correlation, `budget_multiplier` (0.3/0.5), ATR stop/take-profit seviyeleri |
| `app/routers/*` (16 dosya) | ~1300 | **YÜKSEK** | `autonomous.py` (para), `balance.py` (para), `portfolio.py`, `watchlist.py`, `screener*.py`. HTTP auth/kimlik, 400/404/422 yolları |
| `app/services/balance_service.py` | 191 | **KRİTİK** | `record_position_opened/closed` (cash düş/ekle), `ensure_portfolio`, `reset_balance`, `withdraw` yetersiz bakiye `ValueError`. **Para doğruluğu** |
| `app/services/market_data.py` | 225 | **YÜKSEK** | `get_live_prices` cache TTL, BIST/non-BIST ayırımı, `get_macro_indicators`, `macro_market_assessment`, `format_macro_markdown` (VIX ters sinyal) |
| `app/agents/research_team.py` | 277 | **YÜKSEK** | Bull/Bear skorları, consensus, `_risk_reward_label`, conflict tespiti — `_gather_candidates`'ta adayları zenginleştirir, kararları etkiler |
| `app/skills/stock_analysis.py` | 453 | **KRİTİK** | Tek hisse tam analiz: pipeline fallback, MA20 bias, conclusion, LLM reasoning parse, fair value, prediction kaydı |
| `app/services/regime_detector.py` | ~150 | ORTA | `detect()` → Kelly bütçesi `adjust_for_regime` (bear'da küçültme) |
| `app/services/position_sizing.py` | ~120 | ORTA | `kelly_position_size`, `fractional_kelly`, `get_position_budget` — alım büyüklüğü |

---

## 4. Kritik Fonksiyonlar — Test Edilmeyenler

### Para işlemleri (en yüksek öncelik)
1. **`autonomous_agent.execute_buy`** — cash yetersizse `{"success": False}`; pozisyon + `record_position_opened` + `TradingDecision` log + commit. Para düşme doğruluğu test edilmiyor.
2. **`autonomous_agent.execute_sell`** — pozisyon sahiplik guard (`pos.portfolio_id != portfolio_id` → red), `record_position_closed` + P/L hesabı.
3. **`balance_service.record_position_opened/closed`** — portfolio_id'li ve legacy iki kol; cash round tutarlılığı; eksik portföyde `ValueError`.
4. **`balance_service.withdraw`** — yetersiz bakiye `ValueError` guard.
5. **`balance_service.ensure_portfolio`** — bilinmeyen slug `ValueError`; config'den otomatik oluşturma.
6. **`balance_service.reset_balance`** — sadece o portföyün tx'lerini sil, cash sıfırla.
7. **`autonomous_agent.get_portfolio`** — total_cost/market_value/P/L hesabı; fiyat düşemeyen pozisyonlar entry_price'a düşer.
8. **`autonomous_agent._cleanup_stuck_positions`** — delisted/yfinance hatası → breakeven kapatma; **kritik**: `record_position_closed(db, pos_id, proceeds, ticker)` **portfolio_id olmadan çağrılıyor** (legacy yola düşer — muhtemelen bug, test ile yakalanmalı).

### Veto / risk mantığı
9. **`risk_manager.evaluate`** — vol veto (budget×0.3), sector limit (count-bazlı, value değil), correlation (aynı sektör ≥2 → 0.5), penny stock uyarısı, `approved` = veto yok.
10. **`risk_manager.atr_stop_levels`** — vol yokken %3 varsayılan ATR; stop tabanı `entry*0.85`.
11. **`risk_manager.check_sector_exposure`** — `new_sector_pct > max` sınırı, `total_positions==0` erken çıkış.

### Karar mantığı
12. **`autonomous_agent._rule_based_decide`** — RSI>75 sell, stop-loss <-15% sell, composite<40 sell, alımda `score>=60 && rsi<65 && mom>-5`, Kelly bütçe × risk çarpanı, `qty = max(1, int(budget/price))`.
13. **`autonomous_agent._llm_decide_with_llm`** — JSON parse regex, buy/sell exec, LLM hatasında `_rule_based_decide`'a düşüş.
14. **`autonomous_agent._execute_pending_orders`** — piyasa açıkken buy/sell gerçekleştirme, fiyat ≤0 atla, başarısız emri cancel.
15. **`autonomous_agent._deep_analyze_and_queue`** — piyasa kapalıyken `PendingOrder` oluşturma; `conclusion` + composite ≥60 filtresi; `qty = max(1, int(budget/price))`.
16. **`orchestrator.run_pipeline / run_deep_pipeline`** — çift çalışma RuntimeError, Stage 1 boş → boş rapor, `_persist` DB commit, NaN sanitize.

---

## 5. `pytest.ini` — Coverage Kapsamı Analizi

```ini
[pytest]
testpaths = tests
python_files = test_*.py
asyncio_mode = auto
addopts = --cov=app --cov-report=term-missing -q
```

- **`--cov=app` doğru hedeflenmiş** — tüm paketi ölçüyor, tek modül seçmiyor. %22 düşük çünkü app çok büyük (92 dosya, 7379 stmt) ve kritik 10+ modül hiç import edilmiyor.
- **Eksik:**
  - `--cov-report=html` / `xml` yok → CI'da okunabilir rapor üretilmiyor (yalnızca term-missing).
  - `--cov-fail-under` yok → coverage düşüşü pipeline'ı **bloke etmiyor** (ör. %22'nin %18'e düşmesi fail vermez).
  - `--cov-branch` yok → dal kapsamı ölçülmüyor; %22 stmt bile fazla iyimser.
  - `testpaths` + `python_files` varsayılan, sorun yok. `asyncio_mode=auto` isabetli.
  - `tests/`'te **conftest.py yok** → DB fixture'ı, TestClient, auth override yok. Entegrasyon testleri için altyapı eksik.

---

## 6. Mevcut Test Kalitesi

**Güçlü yanlar:**
- Mock'lar genelde doğru seviyede: `safe_ticker_history`/`safe_download`/`generate` monkeypatch — ağ ve LLM çağrısı yok, deterministik.
- Saf fonksiyonlarda sınır değerleri iyi (ör. `payout_status` 0.40/0.80 sınırları, `detect_pattern` doji %5, `income_rating` eşikleri parametrize).
- Edge case'ler saf fonksiyonlarda mevcut: `None`/boş/`0`/negatif girişler (bias_pct, format_pl, cagr_5y, payout_ratio).

**Zayıf yanlar:**
1. **Mock'lar gerçekçiliği düşük** — yfinance `MultiIndex` sütun yapısı (Close/Volume iki katmanlı) birçok yerde tek-seviye DataFrame ile taklit ediliyor; `test_alpha_generator`'da açıkça "create single-level for test" notu var. `market_data`/`cross_sectional`'ın gerçek yfinance yanıtına karşı davranışı doğrulanmamış.
2. **DB yok, conftest yok** — 211 testin hiçbiri tablo yazmıyor. Para işlemleri, pending order, TradingDecision, Report kaydı doğrulanmamış. `sqlite://` in-memory DB fixture'ı en büyük tek eklenti olurdu.
3. **Assertion kalitesi eşit değil** — `test_hmm_regime.test_adaptive_weights_in_bull` ağırlık **anlamını** (momentum>fundamental) değil sadece toplam=1'i doğruluyor. `test_alpha_generator` `volume_ratio != 1.0` gibi zayıf assert kullanıyor (her şeyden farklı olabilir).
4. **`test_placeholder.py`** saf `assert True` — silinmeli veya gerçek teste dönüştürülmeli.
5. **Yorumlar İngilizce/Türkçe karışık** ve bazı assert yorumları yanıltıcı (ör. `test_skills_kline` hammer yorumu hesap yapmadan "false (eşit)" diyor).
6. **`test_backtest` 3 test** — en zayıf dosya; `max_dd`, `vol`, short-position, NaN path'leri yok.
7. **Sert kodlanmış büyüklükler** — `test_screener_service` `len(tickers) > 100`; evren değişince kırılır, anlamlı değil.

---

## 7. En Kritik 10 Test Boşluğu (Öncelik Sırasıyla)

| # | Önerilen Test | Dosya | Risk | Açıklama |
|---|---|---|---|---|
| 1 | `test_execute_buy_deducts_cash_and_logs_decision` | `autonomous_agent` | KRİTİK | Pozisyon açılır, Portfolio.cash düşer, BalanceTransaction + TradingDecision yazılır; yetersiz bakiyede `success=False` ve DB'ye hiçbir şey yazılmaz |
| 2 | `test_execute_sell_credits_cash_and_blocks_foreign_position` | `autonomous_agent` | KRİTİK | `record_position_closed` + cash ekleme + P/L; başka portföyün pozisyonu reddedilir (`portfolio_id` mismatch guard) |
| 3 | `test_risk_manager_evaluate_vetoes_high_volatility` | `risk_manager` | KRİTİK | vol ≥40 → `approved=False` + `adjusted_budget_pct=0.3`; sector limit aşımı → veto; korrele pozisyon → 0.5; penny stock uyarısı |
| 4 | `test_rule_based_decide_sells_overbought_buys_eligible` | `autonomous_agent` | KRİTİK | RSI>75/PL<-15% satar; skor≥60+RSI<65 alır; Kelly bütçe × risk çarpanı; `qty=max(1,int(budget/price))` |
| 5 | `test_balance_record_position_updates_cash_atomically` | `balance_service` | KRİTİK | open→cash düş, close→cash ekle, tx kaydı; eksik portfolio_id → `ValueError`; legacy kol çalışır |
| 6 | `test_stock_analysis_run_bias_blocks_buy` | `stock_analysis` | KRİTİK | Mock'lu stage1/2 ile: bias>5% → conclusion hold (buy değil); pipeline boşsa yfinance fallback; data_missing listesi doğru |
| 7 | `test_orchestrator_persist_sanitizes_nan_picks` | `orchestrator` | KRİTİK | `_persist` NaN/Inf pick'i DB'ye yazarken sanitize eder; Stage 1 boş → boş rapor; `run_pipeline` çift çağrı → RuntimeError |
| 8 | `test_pending_orders_executed_on_market_open` | `autonomous_agent` | KRİTİK | Piyasa açıkken pending buy/sell gerçekleşir; fiyat ≤0 atlanır; başarısız emir `cancelled` olur |
| 9 | `test_market_data_cache_ttl_and_bist_fallback` | `market_data` | YÜKSEK | Cache TTL içinde tek fetch; `.IS` ticker bireysel indirilir; bozuk veri → `price: None`; `macro_market_assessment` VIX ters sinyal + format_macro_markdown tablo |
| 10 | `test_research_team_consensus_and_conflicts` | `research_team` | YÜKSEK | `_bull_case`/`_bear_case` sınırlar, `consensus=(bull-bear+100)/2`, `_risk_reward_label` 5 profil, `_detect_conflicts` 4 çatışma senaryosu |

**Yedek adaylar:** `_cleanup_stuck_positions` breakeven kapatma (portfolio_id eksikliği ile birlikte — bug şüphesi), `balance_service.withdraw` yetersiz bakiye, `_deep_analyze_and_queue` pending emir oluşturma + `qty=max(1,int())` sıfıra yuvarlama, router'larda 400/404 yolları (otomatik portfolio slug, bilinmeyen position).

---

## 8. Öneriler (Kısa)

1. **`tests/conftest.py` ekle** — in-memory `sqlite://` + tüm modellerin `create_all` fixture'ı, `TestClient` + auth override. Bu tek dosya 7/10 kritik boşluğu açılabilir yapar.
2. **Coverage gate** — `pytest.ini`'ye `--cov-fail-under=25` ve `--cov-report=html` ekle; hedefi kademeli %40 → %60'a çıkar.
3. **`_cleanup_stuck_positions`'ın `record_position_closed` çağrısını incele** — `portfolio_id` parametresi verilmiyor, legacy yola düşüyor; olası cash tutarsızlığı.
4. **`test_placeholder.py` sil.**
5. **Önce para akışını test et** (1, 2, 5 numaralı boşluklar) — gerçek kayıp riski orada.
