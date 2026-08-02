# ORBIS FINAI — Önceki Oturum Agent Bulguları (Konsolide)

> Bu rapor, önceki oturumda (2 saat önce) çalışıp tamamlanan 6 uzman agent'ın chat'e teslim ettiği bulguları konsolide eder. Dosya tabanlı yeni analizler için: GÜVENLIK_RAPORU.md, TEST_KAPSAM_RAPORU.md, PERFORMANS_RAPORU.md, VERI_DOGULUK_RAPORU.md.

## 1. Güvenlik (agent: dove/security-analyst)

### Kritik
| # | Bulgu | Yer | Düzeltme |
|---|-------|-----|----------|
| S1 | **FERNET_KEY yoksa LLM API key'leri DB'de plaintext** — `get_decrypted_api_key()` fernet yoksa raw döner, `set_encrypted_api_key()` raw saklar | `models/llm.py:13-22,45-64` | **KABUL EDİLMİŞ RİSK (2026-08-02)** — kullanıcı zorunluluğu kaldırdı; şifreleme altyapısı duruyor, FERNET_KEY set edilirse otomatik devreye girer |
| S2 | **Tek paylaşımlı API key — kullanıcı bazlı auth yok** — tüm admin işlemleri aynı `API_KEY`'e güveniyor; session/JWT/MFA yok | `middleware.py:28` | Multi-user planlanana kadar kabul edilebilir; prod'da API_KEY zorunlu kıl |

### Orta
| # | Bulgu | Yer |
|---|-------|-----|
| S3 | **SSRF riski** — provider test endpoint'i (`admin.py api_test_provider`) keyed provider base_url'e HTTP çağrısı yapıyor; URL kullanıcı kontrolünde | `admin_service.py:131` test_provider_connection |
| S4 | API_KEY boşsa tüm auth kapalı (`.env.example` "local only" notu ama docker prod'da boş kalabilir) | `middleware.py:20-22` |

### Pozitif
- `_safe_compare` constant-time (length-safe `compare_digest`) ✓
- CORS sabit allowlist (2 origin) ✓
- slowapi 120/min rate limit ✓
- `eval`/`shell`/`pickle`/`yaml.load` sıfır kullanım ✓
- SQLAlchemy parametreize (SQL injection yüzeyi yok) ✓
- Destructive reset `X-Confirm-Reset` header guard ✓

## 2. Test Kalitesi (agent: fish/test-quality-analyst)

### Kapsanan (18 backend dosya, ~193 test)
- Services: backtest, portfolio_optimizer (kısmi), prediction_engine (feature+heuristic), cross_sectional, hmm_regime, ic_tracker, alpha_generator (yalnız volume anomaly), web_search (parser), yf_utils (retry), screener_service (yalnız universe)
- Agents: fundamental_agent (`_score_*`), report_agent (`_narrative_for`, `_build_rich_summary`)
- Skills: dividend, kline, rumor, stock_analysis (`_rules`), skill_router (anti-hallucination — en iyi test)

### Kritik Boşluklar
| Boşluk | Risk |
|--------|------|
| `autonomous_agent.py` (48.6KB) — **sıfır test** | Para hareketi: execute_buy/sell, pending orders, Kelly, veto — hiçbiri doğrulanmıyor |
| 15 router — **sıfır API testi** | Endpoint contract'ları, auth, rate limit test edilmiyor |
| `technicals.py` — sıfır test | RSI/MACD/Bollinger hesapları doğrulanmamış |
| `balance_service.py` — sıfır test | Bakiye düş/ekle, çoklu portföy cash |
| `risk_manager.py` — sıfır test | Veto mantığı, sector exposure, ATR stop |

### ROADMAP Uyumu
- `portfolio_optimizer.py` entegre (autonomous_agent.py:799 `allocate_buy_budgets`) ✓
- Eksik: `optimize_for_tickers` wrapper, `/api/portfolio/optimize` endpoint, `correlation_matrix` skill endpoint — MARKOWITZ_TODO'nun API+frontend kısmı tamamlanmamış

## 3. Backend Mimari (agent: crocodile/backend-architect)

- Monolitik FastAPI, 5 katman (routers → services → agents → models → db)
- "Sağlam temelli fonksiyonel monolit"
- En kritik riskler: **scheduler thread'lerde asyncio.run**, orchestrator singleton
- (Detay: ANALIZ_RAPORU.md M1-M3 ile örtüşüyor)

## 4. Frontend (agent: eagle/frontend-analyst)

- App Router, tüm sayfalar `"use client"` — **server component yok** (SEO + ilk yükleme maliyeti)
- **Kritik bulgu: `useLivePrices.ts` SSE değil, 3s REST polling** — backend `/api/prices/stream` SSE endpoint'i var ama kullanılmıyor (ANALIZ_RAPORU.md M9)
- 13 skill 11 tab ile tam entegre (SkillPanel.tsx)
- Terminal teması (amber/black) tutarlı, globals.css CSS değişkenleri

## 5. Veri Kalitesi (agent: dog/data-quality-analyst)

- Tek veri kaynağı: **yfinance** — rate-limit/kesilme riski tek nokta (yf_utils retry + cache ile azaltılmış)
- HMM state probs + getiri observasyonları doğrulandı
- (Detay: VERI_DOGULUK_RAPORU.md'de yeni agent'ın derin formül doğrulaması)

## 6. Agent Sistemi (agent: cricket/agent-system-analyst)

- ORBIS_AI_AGENT_ANALIZI.md (88 satır, dosya:satır referanslı) — 10 zayıflık + skor mantığı + pipeline
- Özet: NewsAnalyst/BullBear/RiskManager main pipeline'da kullanılmıyor; ScannerAgent boş; IC tek faktör
