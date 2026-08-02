# ORBIS FINAI — Kapsamlı İnceleme Özeti

Tarih: 2026-08-02 · Yöntem: 6 paralel analiz ajanı (swarm) + manuel inceleme

## Rapor Haritası (ayrıntılar ilgili dosyada)

| Rapor | Dosya | Kapsam |
|---|---|---|
| Mimari & Kod Kalitesi | `ANALIZ_RAPORU.md` | Pipeline, agent mimarisi, mimari borçlar |
| AI Agent Sistemi | `ORBIS_AI_AGENT_ANALIZI.md` | Skor mantıkları, SkillRouter, LLM fallback |
| Veri Doğruluğu | `VERI_DOGULUK_RAPORU.md` | Lynch/PEG, prediction engine, finansal motor |
| Performans | `PERFORMANS_RAPORU.md` | yfinance yüzeyi, sıralı pipeline, thread eşzamanlılık |
| Güvenlik | `GUVENLIK_RAPORU.md` | Fernet, API key, SSRF, auth |
| Test Kapsamı | `TEST_KAPSAM_RAPORU.md` | 193 test, kritik boşluklar |
| Frontend | *(chat'te teslim, dosyasız)* | SSE değil 3s polling, 3 kopya kümesi, any sızıntıları |

## En Kritik Bulgular (düzeltme önceliği)

### 1. Güvenlik — KRİTİK
- **S1.** `FERNET_KEY` yok → LLM API key'leri DB'de düz metin (`models/llm.py:13-22`)
- **S2.** Tek paylaşımlı API key, kullanıcı auth yok → tüm admin işlemleri aynı key'e güveniyor
- **S3.** SSRF: provider test endpoint'i keyed URL'ye HTTP çağrısı (Orta)
- **S4.** `API_KEY` boşsa tüm auth kapalı

### 2. Hesaplama Bugları — YÜKSEK
- **RSI düz seri bug'ı (3 dosyada aynı):** `avg_loss == 0` → RSI=100 (aşırı alım). Doğru: 50/nötr. `screener_service.py:128`, `~215`, `prediction_engine.py:99`, `technicals.py:45`. Tek taraflı fiyat hareketinde screener tüm hisseleri yanlış eler.
- **DCF ZeroDivision:** `wacc <= terminal_growth` ise crash/negatif TV (`fair_value.py:55`). `shares_outstanding` dead param.
- **ensemble weights eziliyor:** ilk dict dead code (`fair_value.py:105-112`)
- **Piotroski:** no-prev-data "varsayılan +1" F-Score'u 9'a şişirir
- **dividendYield birim:** 1.5 → "%150" yorumlanıyor (aslında %1.5)

### 3. Mimari — YÜKSEK
- `BullBearResearcher`, `NewsAnalyst`, `RiskManager` ana pipeline'da **kullanılmıyor** (sadece autonomous agent'ta)
- IC tracker tek faktör ("agent_confidence")
- Research memory pipeline'a bağlı değil
- Scheduler thread'leri ↔ async pipeline eşzamanlılık riski
- Agent zinciri tamamen sıralı; `cross_sectional` + `alpha_generator` 0.3s sleep'ler

### 4. Performans — YÜKSEK
- XGBoost `n_jobs=-1` + her çağrıda retrain (CPU starvation)
- Tek veri kaynağı yfinance; semaphore yok → rate-limit riski
- TRY/USD birim karışıklığı (BIST'te EPS USD okunabilir)

### 5. Frontend
- `useLivePrices.ts` SSE değil — 3s HTTP polling; `EventSource` hiç kullanılmıyor, `LivePricesEvent` ölü kod
- 3 kopya bileşen kümesi (PortfolioStatusBar/AgentPortfolioCard, WatchlistBar/Widget, bist grid)
- Tümü client-render, SSR yok; `.catch(()=>{})` yaygın

### 6. Test Kapsamı
- **`autonomous_agent.py` (48.6KB) sıfır test** — para-hareket katmanı çıplak
- 15 router'da sıfır API testi
- En yüksek ROI: autonomous_agent trade akışı (in-memory SQLite + price mock), `technicals.py`
- ROADMAP uyumu kısmi: `correlation_matrix`/`optimize_for_tickers`/`/optimize` ve `test_correlation_matrix.py` eksik; Aşama 5 `growth_agent`/`value_agent` yok

## Olumlu
- 6-tier LLM fallback (DB → Ollama → Groq → Gemini → OpenAI → Claude) + VLM/embedding zincirleri
- SkillRouter 7 anti-hallucination katmanı; bias >%5 → buy engeli
- Test altyapısı: saf fonksiyon + 4 mock deseni, 193 test
- Constant-time compare, sabit CORS listesi, rate limit, parametreize SQL

## Önerilen Sıra
1. Güvenlik S1-S2 (key encryption + auth)
2. RSI bug'ı (4 nokta) + DCF ZeroDivision
3. autonomous_agent testleri
4. Pipeline'a BullBear/NewsAnalyst entegrasyonu
5. XGBoost cache / n_jobs sınırlama
