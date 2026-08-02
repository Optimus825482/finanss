# ORBIS FINAI — AI Agent Sistemi Analiz Raporu

## (a) Agent Mimarisi & Pipeline Akışı

**2-stage pipeline** (`orchestrator.py:72-90`):

```
Universe (100+ ticker)
  → Stage 1: Technical Pre-screen (screener_service.stage1_prescreen)
  → Stage 2: FundamentalAgent → SentimentAgent → RiskAgent → ReportAgent
  → DB persist (Report + StockPick)
```

- **Stage 1** (`screener_service.py:65`): momentum, hacim, fiyat filtreleri ile 100+ hisseden ~8 aday seçer.
- **Stage 2** (`screener_service.py:304`): seçilen adaylar sırayla 3 agent'ten geçer, sonra ReportAgent composite skor + fair value + LLM enrichment yapar.
- **Deep Batch** (`orchestrator.py:120`): alternatif pipeline, stage 2 sonrası Fair Value + Prediction + LLM ekler.

**Autonomous Agent** (`autonomous_agent.py:110-115`): NewsAnalyst'i de içeren 5-agent sıralı pipeline kullanır. BullBearResearcher + RiskManager da burada çağrılır (satış kararları).

## (b) Her Agent'ın Sorumluluğu & Skor Mantığı

| Agent | Dosya | Skor | Açıklama |
|-------|-------|------|----------|
| **ScannerAgent** | `agents/scanner_agent.py:9` | — | Sentinel only. Stage 1 progress banner. İçi boş. |
| **FundamentalAgent** | `agents/fundamental_agent.py:39` | 0-100 | PE (10-25=90p), Revenue Growth (>%20=95p), ROE (>%20=90p), Debt/Equity (<50=%85p) ortalaması. Piotroski F-Score ≥7 bonus +5, ≤3 penalty -5. |
| **SentimentAgent** | `agents/sentiment_agent.py:29` | 0-100 | VADER compound avg (-1..1) → `(avg+1)*50`. Veri yoksa 50.0 nötr. |
| **NewsAnalyst** | `agents/news_analyst.py:36` | 0-100 | VADER + burst detection (son 24s/7g) + sentiment trend (ilk/ikinci yarı) + event keyword (earnings/merger/legal/product). News_score = VADER ± burst/trend adjustment. |
| **RiskAgent** | `agents/risk_agent.py:24` | 0-100 | Volatility (0.45) + Max Drawdown (0.35) + Beta (0.20). Yüksek skor = yüksek risk. |
| **RiskManager** | `agents/risk_manager.py:48` | veto/bool | Pre-trade: volatility threshold, sector exposure (max %40), correlation (max 0.75), ATR trailing stop. Veto yetkisi + budget multiplier. |
| **BullBearResearcher** | `agents/research_team.py:21` | 0-100 | Bull: momentum, scores, PE, sentiment, RSI, fair value. Bear: risk, volatility, PE, momentum, RSI, sentiment. Consensus = `(bull - bear + 100) / 2`. Risk/ödül profili + conflict detection. |
| **ReportAgent** | `agents/report_agent.py:147` | composite | Composite = `fundamental×0.40 + sentiment×0.30 + (100-risk)×0.30`. Fair Value ekler, makro bağlam, LLM enrichment (hedef fiyat + gerekçe). |

**Scoring weights** (`config.py:172`): fundamental 0.40, sentiment 0.30, risk 0.30.

## (c) Bull/Bear Research Team

**BullBearResearcher** (`research_team.py:21`) main pipeline'da **kullanılmaz** — sadece `autonomous_agent.py:453`'te çağrılır.

- **Bull case** (`research_team.py:68`): 6 faktör ağırlıklı toplam. Momentum +5% üstü +35p, composite ≥80 +30p, fundamental ≥80 +25p, PE <10 +20p, RSI 30-50 +10p, fair value margin >%20 +20p.
- **Bear case** (`research_team.py:154`): 7 faktör. Risk ≥70 +35p, volatility >%50 +25p, PE >40 +25p, momentum <-5% +30p, RSI >75 +25p.
- **Consensus**: 0-100 scale. `risk_reward_profile`: strong_opportunity / good_opportunity / neutral / risky / high_risk.
- **Conflict detection**: momentum vs RSI divergence, high score vs high risk, high PE vs strong fundamentals.

## (d) Skill Sistemi & Tool Router Anti-Hallucination

**12 skill** (`skill_tools.py:154-192`): analyze_stock, analyze_dividend, scan_rumors, manage_watchlist, analyze_kline, sector_rotation, correlation_matrix, insider_activity, unusual_options, earnings_surprise, seasonality, fair_value.

**SkillRouter** (`skill_router.py:128`) — 7 anti-hallucination önlemi:

1. **Prompt'ta örnek JSON yok** (`skill_router.py:7`): LLM kopyalayıp hallucinate etmesin diye.
2. **Pydantic strict=True** (`skill_router.py:9`): ekstra alan reject, tip coercion yok.
3. **Whitelist** (`skill_router.py:241`): tool adı `_tools` dict'inde tam eşleşme.
4. **Retry with error feedback** (`skill_router.py:189-214`): parse/validation hatasında LLM hatayı görür, düzeltir.
5. **max_turns + max_retries** (`skill_router.py:135-136`): sonsuz döngü engeli.
6. **Handler kısıtlaması** (`skill_router.py:13`): sadece okuma/DB-yazma, asla kod execute.
7. **Audit log** (`skill_router.py:149`): her çağrı kaydedilir.

**Behavior rules** (`_rules.py:1`): bias (MA20 sapma) >%5 → "buy"/"strong_buy" "hold"'a düşürülür. LLM'e bırakılmaz, Python ile zorunlu kılınır.

## (e) LLM Entegrasyonu & Fallback Stratejileri

**llm_bridge.py** — LiteLLM model-agnostic katman:

- **6 provider**: Ollama, OpenAI, Claude, Gemini, Groq, NVIDIA NIM (DB-registered key rotation).
- **get_default_model()** (`llm_bridge.py:40`): 6-tier fallback: DB provider → Ollama → Groq → Gemini → OpenAI → Claude.
- **generate_vision()** (`llm_bridge.py:182`): VLM for k-line chart analysis. Vision-capable model auto-detect: OpenAI → Claude → Gemini → Ollama.
- **get_embedding()** (`llm_bridge.py:149`): OpenAI → Ollama fallback, ikisi de yoksa None (caller graceful handling).

**Fallback zincirleri**:
- **Rumor sınıflandırma**: LLM → VADER+keyword fallback (`rumor_scanner.py:128`).
- **K-line VLM**: vision model → matplotlib metin teknik analiz (`kline_chart.py:107`).
- **Stock analysis**: full pipeline → yfinance direct → agent pipeline → info dict only (`stock_analysis.py:80-106`).
- **Report LLM enrichment**: best-effort, exception sessiz atılır (`report_agent.py:100`).

## (f) Zayıflıklar & İyileştirme Önerileri

| # | Zayıflık | Dosya | Öneri |
|---|----------|-------|-------|
| 1 | **NewsAnalyst, BullBearResearcher, RiskManager main pipeline'da kullanılmıyor** | `orchestrator.py:79-82` | Stage 2'ye NewsAnalyst + BullBearResearcher'ı ekle. SentimentAgent'ı NewsAnalyst ile değiştir. |
| 2 | **ScannerAgent içi boş** | `scanner_agent.py:9` | Stage 1 detaylarını (prescreen sonuçları, hangi ticker'lar elendi) raporla. |
| 3 | **IC tracker tek faktör** | `ic_tracker.py:161` | Her agent'ın skorunu ayrı faktör olarak track et (fundamental_ic, sentiment_ic, risk_ic). |
| 4 | **Research memory pipeline'da kullanılmıyor** | `memory_service.py:120` | Stage 2'de `build_context_for_ticker()` çağrılıp hafıza bağlamı LLM enrichment'e verilebilir. |
| 5 | **VADER-only sentiment sığ** | `sentiment_agent.py:12` | FinBERT veya LLM-based sentiment'e geç. NewsAnalyst'in LLM classify'i reuse edilebilir. |
| 6 | **Embedding yoksa None döner, caller kontrol etmez** | `llm_bridge.py:157` | `memory_service.py:162` embedding None kontrolü yapıyor ama `search_similar_memories` embedding yoksa [] döner — bu sessiz hata. |
| 7 | **Agent scoring test coverage yok** | `agents/fundamental_agent.py:19-35` | `_score_pe`, `_score_growth` gibi pure fonksiyonlar test edilebilir ama test yok. |
| 8 | **RiskManager dynamic sector mapping yok** | `risk_manager.py:44-63` | SECTOR_MAP statik dict. Yeni ticker'lar "other" kategorisine düşer. |
| 9 | **Web search async değil** | `rumor_scanner.py:323` | `fetch_rumor_format` async olabilir ama `asyncio.to_thread` ile sarılmış — performans kaybı. |
| 10 | **Orchestrator singleton pattern** | `orchestrator.py:181` | `orchestrator = Orchestrator()` global. Concurrent pipeline çalıştırılamaz. |