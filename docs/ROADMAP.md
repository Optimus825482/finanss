# ORBIS FINAI — Geliştirme Yol Haritası (Roadmap)

> **Uzun ad:** ORBIS Finance Analyze Team  
> **Marka:** ORBIS FINAI  
> **İlke:** Tamamen açık kaynak ve ücretsiz kaynaklarla, terminal teması korunarak,  
> kurumsal düzeyde AI destekli yatırım araştırma platformu.

---

## İÇİNDEKİLER
1. [Mevcut Durum Analizi](#1-mevcut-durum-analizi)
2. [Mimariden Çıkarılanlar (YAGNI)](#2-mimariden-çıkarılanlar-yagni)
3. [Qlib & RD-Agent'ten Alınacaklar](#3-qlib--rd-agentten-alınacaklar)
4. [Hedef Mimari](#4-hedef-mimari)
5. [Ücretsiz Veri Kaynakları](#5-ücretsiz-veri-kaynakları)
6. [Aşamalı Geliştirme Planı](#6-aşamalı-geliştirme-planı)
7. [Riskler ve Azaltma](#7-riskler-ve-azaltma)

---

## 1. MEVCUT DURUM ANALİZİ

### 1.1. Halihazırda Çalışan Sistem

| Katman | Durum | Detay |
|--------|-------|-------|
| **Backend** | ✅ Canlı | FastAPI, 5 ajan, SQLite, yfinance 1.5.1 |
| **Frontend** | ✅ Canlı | Next.js 14, terminal teması (amber/black), Tailwind |
| **Orkestratör** | ✅ Basit | Sıralı ajan zinciri (scanner → fundamental/sentiment/risk → report) |
| **Veri** | ✅ Temel | yfinance üzerinden canlı fiyat + geçmiş |
| **Zamanlama** | ✅ Cron | APScheduler ile günlük 08:00 raporu |
| **Komponentler** | ✅ | SignalChain, StockCard, WatchlistPanel, PortfolioPanel |

### 1.2. Mevcut 5 Ajan

| Ajan | Yaptığı İş | Kullandığı Veri |
|------|-----------|-----------------|
| **ScannerAgent** | Momentum taraması, hacim analizi | yfinance geçmiş fiyat |
| **FundamentalAgent** | F/K, ROE, gelir büyümesi, borçluluk | yfinance bilanço |
| **SentimentAgent** | Haber başlıkları VADER duygu skoru | yfinance news |
| **RiskAgent** | Volatilite, max drawdown, beta, risk skoru | Geçmiş fiyat + S&P 500 |
| **ReportAgent** | Türkçe piyasa özeti, pick listesi | Diğer 4 ajandan gelen sentez |

### 1.3. Güçlü Yönler
- Terminal teması benzersiz ve akılda kalıcı
- Basit, anlaşılır kod yapısı
- Türkçe çıktılar (raporlar, UI)
- Sıfır maliyetle çalışıyor
- Anlık fiyat + portföy takibi çalışıyor

### 1.4. Eksikler
- LLM entegrasyonu yok (raporlar şablon/istatistik bazlı)
- Chat/doğal dil arayüzü yok
- Teknik analiz göstergeleri yok (RSI, MACD, Bollinger)
- Backtesting yok
- Hisse karşılaştırma yok
- Fiyat tahmin modeli yok
- Veri zenginleştirme yok (makro, insider, SEC filing)
- Kullanıcı oturumu yok (tek kullanıcılı)
- Bildirim sistemi yok

---

## 2. MİMARİDEN ÇIKARILANLAR (YAGNI)

SEEKER AI planındaki şu bileşenler **şu an için gereksiz**, ileri aşamalarda değerlendirilebilir:

| Bileşen | Neden Çıkarıldı | Ne Zaman Eklenir |
|---------|----------------|-------------------|
| TimescaleDB | SQLite günlük/veri için yeterli. 5+ yıl geçmiş + dakikalık veri gerekirse. | Aşama 4+ |
| Redis | Gerçek zamanlı veri yok. Canlı streaming eklenince. | Aşama 4+ |
| Celery + Redis Queue | FastAPI BackgroundTasks şu an yeterli. Paralel kullanıcı talebi artınca. | Aşama 4+ |
| Pinecone/ChromaDB | Vektör arama gerekli değil. Semantik rapor araması eklenince. | Aşama 5+ |
| Kubernetes/Traefik | Tek sunucu yeterli. Multi-tenant SaaS olunca. | Aşama 6+ |
| React Native mobil | Önce PWA yeterli. Native push notification gerekince. | Aşama 6+ |
| LangGraph + CrewAI + LangSmith | Pydantic AI veya basit bir ajan framework yeterli. 3 framework overkill. | Mimaride sadeleştirildi |
| OAuth 2.0 + sosyal login | Tek kullanıcılı başlangıç için yok. Multi-user olunca. | Aşama 3+ |
| Meta Prophet | LSTM veya basit regresyon yeterli. Ensemble tahmin gerekince. | Aşama 4+ |
| AWS S3 | Dosya depolama yok. Model ağırlıkları/rapor arşivi gerekince. | Aşama 5+ |

---

## 3. QLIB & RD-AGENT'TEN ALINACAKLAR

### 3.1. Microsoft Qlib'ten Faydalanılacaklar

| Özellik | ORBIS FINAI'ye Uyarlama |
|---------|------------------------|
| **Qlib veri formatı** (bin/gzip'li array) | Geçmiş fiyat verilerini hızlı yüklemek için. Backtesting aşamasında kullanılabilir |
| **Factor expression engine** | Teknik göstergeleri formül diliyle tanımlama (RSI, MACD hesaplama kolaylığı) |
| **Backtest framework** (backtest.py) | Kendi backtesting modülümüz için referans mimari |
| **Model zoo** (LightGBM, XGBoost, LSTM) | Hazır model implementasyonlarından ilham alma |
| **Alpha finding pipeline** | Sinyal → model → backtest akışı |
| **Rolling training** | Model drift önleme için kayan pencere eğitimi |

**Pratik kullanım:** Qlib'in veri katmanını ve model yönetimini olduğu gibi kullanmak yerine, mimarisinden ilham alıp kendi hafif implementasyonumuzu yapacağız. Qlib ağır ve finans domain'ine çok bağlı — ORBIS FINAI'nin basitliğini bozar.

### 3.2. Microsoft RD-Agent'tan Faydalanılacaklar

| Özellik | ORBIS FINAI'ye Uyarlama |
|---------|------------------------|
| **R + D döngüsü** (Research → Development) | Scanner (R) + Agent pipeline (D) olarak zaten var. Formelleştirilecek |
| **LiteLLM entegrasyonu** | Tek arayüzle birden çok LLM sağlayıcısına bağlanma (OpenAI/Claude/yerel) |
| **Factor extraction from reports** | Haber/rapor metinlerinden otomatik faktör çıkarma |
| **Feedback loop** | Backtest sonuçlarıyla model iyileştirme döngüsü |
| **Copilot vs Agent modu** | Kullanıcı manuel tetikleme vs tam otomatik pipeline |

### 3.3. Diğer Açık Kaynak Projeler

| Proje | Ne İşe Yarar | ORBIS FINAI'de Kullanım |
|-------|-------------|------------------------|
| **[FinBERT](https://github.com/ProsusAI/finBERT)** | Finansal duygu analizi | VADER yerine daha profesyonel sentiment |
| **[OpenBB Terminal](https://github.com/OpenBB-finance/OpenBB)** | Açık kaynak Bloomberg terminali | Veri sağlayıcı entegrasyonları, ekonomi takvimi |
| **[TA-Lib](https://github.com/TA-Lib/ta-lib-python)** | 150+ teknik gösterge | RSI, MACD, Bollinger, Ichimoku |
| **[Zipline-Reloaded](https://github.com/stefan-jansen/zipline-reloaded)** | Backtesting motoru | Strateji backtest altyapısı |
| **[streamlit](https://github.com/streamlit/streamlit)** | Hızlı veri dashboard | Admin panel, model monitoring (opsiyonel) |
| **[LangChain](https://github.com/langchain-ai/langchain)** | LLM orkestrasyon (tek başına yeterli) | Chat ajanı + tool calling |
| **[Ollama](https://github.com/ollama/ollama)** | Yerel LLM çalıştırma | API maliyeti olmadan LLM kullanımı |

---

## 4. HEDEF MİMARİ

Sadeleştirilmiş, işlevsel hedef mimari:

```
┌─────────────────────────────────────────────────┐
│              FRONTEND (Next.js 14)               │
│   Terminal teması · Chat paneli · Grafikler      │
│   TradingView Lightweight Charts                 │
└────────────────────┬────────────────────────────┘
                     │ REST + SSE (streaming)
┌────────────────────┴────────────────────────────┐
│           BACKEND (FastAPI)                       │
│                                                    │
│  ┌──────────┐  ┌──────────────────────────────┐  │
│  │  Auth    │  │     AGENT PIPELINE             │  │
│  │  (JWT)   │  │                                │  │
│  └──────────┘  │  RESEARCH LAYER                │  │
│                │  ┌──────────────────────────┐  │  │
│  ┌──────────┐  │  │ Scanner · Fundamental     │  │  │
│  │ Scheduler│  │  │ Sentiment · Risk · Macro  │  │  │
│  │ (APS)    │  │  │ Technicals (yeni)         │  │  │
│  └──────────┘  │  └──────────────────────────┘  │  │
│                │              ↓                  │  │
│  ┌──────────┐  │  EXPERT LAYER                   │  │
│  │Backtest  │  │  ┌──────────────────────────┐  │  │
│  │Engine    │  │  │ Value · Growth · Optimizer│  │  │
│  └──────────┘  │  │ (LLM-powered sentez)      │  │  │
│                │  └──────────────────────────┘  │  │
│  ┌──────────┐  │              ↓                  │  │
│  │LLM Bridge│  │  INTERFACE LAYER                │  │
│  │(LiteLLM) │  │  ┌──────────────────────────┐  │  │
│  └──────────┘  │  │ Chat Agent (LLM + tools)  │  │  │
│                │  │ Report Generator          │  │  │
│                │  └──────────────────────────┘  │  │
│                └──────────────────────────────┘  │
│                                                    │
│  ┌────────────────────────────────────────────┐   │
│  │  DATA LAYER                                 │   │
│  │  SQLite (mevcut) → PostgreSQL (Aşama 3)     │   │
│  │  yfinance · FRED · Finnhub · NewsAPI        │   │
│  └────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────┘
```

**Temel farklar (SEEKER AI planına göre):**
- LangGraph/CrewAI yerine basit Python async pipeline + LLM tool calling
- TimescaleDB/Redis/Pinecone/S3 yok — SQLite/PostgreSQL yeterli
- Celery yok — FastAPI BackgroundTasks + APScheduler
- 3 ajan katmanı net: Research → Expert → Interface
- Terminal teması korunuyor, TradingView grafikleri ekleniyor

---

## 5. ÜCRETSİZ VERİ KAYNAKLARI

### 5.1. Mevcut + Eklenecek

| Kaynak | Tip | Limit | Kullanım |
|--------|-----|-------|----------|
| **yfinance** (mevcut) | Fiyat, bilanço, haber | ~2000 req/saat tahmini | Ana veri kaynağı |
| **[Alpha Vantage](https://www.alphavantage.co)** | Fiyat, FX, teknik, temel | 25 req/gün (ücretsiz) | Temel analiz takviyesi |
| **[Finnhub](https://finnhub.io)** | Fiyat, haber, SEC filing | 60 req/dk (ücretsiz) | Haber + insider trading |
| **[FRED](https://fred.stlouisfed.org)** | ABD makro verileri | Sınırsız (API key ücretsiz) | Faiz, GSYİH, enflasyon |
| **[NewsAPI](https://newsapi.org)** | Haber başlıkları | 100 req/gün (ücretsiz) | Global haber taraması |
| **[Ollama](https://ollama.com)** | Yerel LLM | Sınırsız (kendi donanımın) | Chat agent, rapor sentezi |
| **[TA-Lib](https://ta-lib.org)** | Teknik göstergeler | Sınırsız (kütüphane) | RSI, MACD, Bollinger |

### 5.2. LLM Stratejisi

Öncelik sırası (maliyetsiz → kontrollü maliyet):

1. **Ollama + Llama 3.1/Gemma/Qwen** — tamamen ücretsiz, yerel
2. **Groq Cloud** — ücretsiz tier (Llama 3.1, Mixtral)
3. **Google Gemini API** — ücretsiz tier (günde ~1500 istek)
4. **OpenAI/Claude API** — kontrollü maliyetle, sadece gerekince

---

## 6. AŞAMALI GELİŞTİRME PLANI

### AŞAMA 1: Temel Güçlendirme (2-3 Hafta)

**Amaç:** Mevcut sistemi sağlamlaştır, yeni veri kaynaklarını ekle, teknik analiz ekle.

| # | Görev | Dosyalar | Öncelik |
|---|-------|----------|---------|
| 1.1 | `yfinance` error handling güçlendir — rate limit, retry, fallback | `market_data.py`, `scanner_agent.py` | 🔴 Kritik |
| 1.2 | TA-Lib entegrasyonu: RSI, MACD, Bollinger Bands, SMA/EMA | Yeni: `app/services/technicals.py` | 🟡 Yüksek |
| 1.3 | ScannerAgent'a teknik filtre ekle (RSI < 30 aşırı satım, MACD kesişimi) | `scanner_agent.py` | 🟡 Yüksek |
| 1.4 | FundamentalAgent'a ek metrikler: PEG, P/B, FCF yield | `fundamental_agent.py` | 🟢 Orta |
| 1.5 | Finnhub API entegrasyonu (haber + insider trading verisi) | Yeni: `app/services/finnhub_service.py` | 🟢 Orta |
| 1.6 | Frontend: SignalChain'e ajan durum renkleri + süre göstergesi | `SignalChain.tsx` | 🟢 Orta |
| 1.7 | Frontend: StockCard'a mini sparkline grafiği | `StockCard.tsx` | 🟢 Orta |
| 1.8 | `.env` şablonu güncelle (yeni API key'ler) | `.env.example` | 🟢 Orta |

**Aşama 1 Çıktısı:** Daha sağlam veri çekme, teknik göstergeler, zenginleşmiş scanner.

---

### AŞAMA 2: LLM Entegrasyonu ve Chat Arayüzü (3-4 Hafta)

**Amaç:** Platforma doğal dil etkileşimi kazandır, raporları LLM ile sentezle.

| # | Görev | Dosyalar | Öncelik |
|---|-------|----------|---------|
| 2.1 | LiteLLM entegrasyonu — tek arayüzle çoklu LLM desteği | Yeni: `app/services/llm_bridge.py` | 🔴 Kritik |
| 2.2 | Ollama desteği ekle (yerel ücretsiz LLM) | `llm_bridge.py` | 🔴 Kritik |
| 2.3 | ReportAgent'ı LLM-powered yap — Türkçe piyasa özeti, şablon değil sentez | `report_agent.py` | 🟡 Yüksek |
| 2.4 | StockPick narrative'lerini LLM ile üret | `report_agent.py` | 🟡 Yüksek |
| 2.5 | Backend: `/api/chat` SSE streaming endpoint | `main.py` | 🟡 Yüksek |
| 2.6 | Chat Agent (InterfaceAgent): kullanıcı sorusu → ajan pipeline → yanıt | Yeni: `app/agents/chat_agent.py` | 🟡 Yüksek |
| 2.7 | Frontend: Chat paneli komponenti (terminal temasında) | Yeni: `app/components/ChatPanel.tsx` | 🟡 Yüksek |
| 2.8 | Frontend: Dashboard'a chat panelini ekle | `page.tsx` | 🟡 Yüksek |
| 2.9 | Frontend: Markdown rendering + streaming text animasyonu | `ChatPanel.tsx` | 🟢 Orta |

**Aşama 2 Çıktısı:** Kullanıcı hisse sorabilir, sohbet edebilir, LLM'li rapor üretimi.

---

### AŞAMA 3: Veri Katmanı ve Analiz Derinliği (3-4 Hafta)

**Amaç:** Veri kaynaklarını zenginleştir, hisse karşılaştırma ve derin analiz ekle.

| # | Görev | Dosyalar | Öncelik |
|---|-------|----------|---------|
| 3.1 | PostgreSQL'e geçiş (SQLite'ten migration script) | `database.py`, yeni: `app/migrations/` | 🟡 Yüksek |
| 3.2 | MacroAgent: FRED API ile faiz, enflasyon, GSYİH verisi | Yeni: `app/agents/macro_agent.py` | 🟡 Yüksek |
| 3.3 | Hisse karşılaştırma endpoint'i: `/api/stocks/compare?tickers=AAPL,MSFT` | `main.py`, yeni servis | 🟡 Yüksek |
| 3.4 | Frontend: Karşılaştırma tablosu komponenti | Yeni: `app/components/CompareTable.tsx` | 🟢 Orta |
| 3.5 | FinBERT entegrasyonu (VADER yerine profesyonel sentiment) | `sentiment_agent.py` | 🟢 Orta |
| 3.6 | Tarihsel rapor arama/filtreleme | `main.py`, `page.tsx` | 🟢 Orta |
| 3.7 | Kullanıcı oturumu (JWT auth) — çok kullanıcılı temel | `main.py`, yeni: `app/auth.py` | 🟢 Orta |
| 3.8 | Veri sağlayıcı soyutlama katmanı (yfinance + alpha vantage + finnhub fallback zinciri) | Yeni: `app/services/data_provider.py` | 🟡 Yüksek |

**Aşama 3 Çıktısı:** PostgreSQL, makro veri, hisse karşılaştırma, profesyonel sentiment.

---

### AŞAMA 4: Gelişmiş Analiz ve Görselleştirme (4-5 Hafta)

**Amaç:** Backtesting, portföy optimizasyonu, fiyat tahmini, gelişmiş grafikler.

| # | Görev | Dosyalar | Öncelik |
|---|-------|----------|---------|
| 4.1 | Portföy optimizasyonu (Markowitz MPT, Sharpe Ratio, korelasyon matrisi) | Yeni: `app/services/portfolio_optimizer.py` | 🟡 Yüksek |
| 4.2 | Backtesting motoru (basit, Zipline ilhamlı) | Yeni: `app/services/backtest.py` | 🟡 Yüksek |
| 4.3 | LSTM fiyat tahmin modeli (basit, 1-7 günlük) | Yeni: `app/services/price_predictor.py` | 🟢 Orta |
| 4.4 | Frontend: TradingView Lightweight Charts entegrasyonu | Yeni: `app/components/PriceChart.tsx` | 🟡 Yüksek |
| 4.5 | Frontend: Portföy dashboard — pasta grafik, risk metrikleri | `PortfolioPanel.tsx` (genişletme) | 🟡 Yüksek |
| 4.6 | Uyarı sistemi (teknik sinyal, haber, fiyat eşiği) | Yeni: `app/services/alert_service.py` | 🟢 Orta |
| 4.7 | Frontend: Bildirim paneli | Yeni: `app/components/AlertPanel.tsx` | 🟢 Orta |
| 4.8 | Qlib veri formatı ile geçmiş veri cache (hızlı yükleme) | `data_provider.py` (genişletme) | 🟢 Orta |

**Aşama 4 Çıktısı:** Profesyonel analiz araçları, backtesting, portföy optimizasyonu, gelişmiş grafik.

---

### AŞAMA 5: Expert Agent Katmanı ve Zeka Derinliği (4-6 Hafta)

**Amaç:** İkinci ajan katmanını (Expert) devreye al, multi-perspektif analiz, debate mekanizması.

| # | Görev | Dosyalar | Öncelik |
|---|-------|----------|---------|
| 5.1 | Growth Agent: gelir büyüme trendi, sektör kıyaslama | Yeni: `app/agents/growth_agent.py` | 🟡 Yüksek |
| 5.2 | Value Agent: DCF modeli, içsel değer, marj of safety | Yeni: `app/agents/value_agent.py` | 🟡 Yüksek |
| 5.3 | Expert pipeline: Research çıktısını 3 perspektiften (Value, Growth, Risk) değerlendir | `orchestrator.py` (genişletme) | 🟡 Yüksek |
| 5.4 | Agent debate mekanizması: çelişen görüşler → sentez | `orchestrator.py`, `chat_agent.py` | 🟢 Orta |
| 5.5 | Composite Score v2: Value + Growth + Risk + Technical + Sentiment ağırlıklı | `config.py`, tüm agent'lar | 🟡 Yüksek |
| 5.6 | Otomatik yatırım tezi (Investment Thesis) üretimi | `report_agent.py` (genişletme) | 🟢 Orta |
| 5.7 | Frontend: Multi-perspektif analiz görünümü (her ajanın mini kartı) | Yeni: `app/components/ExpertPanel.tsx` | 🟢 Orta |
| 5.8 | RD-Agent ilhamlı: "Raporu Oku → Faktör Çıkar → Modelle" mini pipeline | Yeni: `app/services/factor_extractor.py` | 🟢 Orta |

**Aşama 5 Çıktısı:** İkinci katman expert ajanları, çok perspektifli analiz, debate sentezi.

---

### AŞAMA 6: Olgunluk ve Ölçeklenebilirlik (Devam Eden)

**Amaç:** Platform olgunluğa ulaştığında eklenecek özellikler.

| # | Görev | Ne Zaman |
|---|-------|----------|
| 6.1 | Redis cache (canlı veri + session) | Gerçek zamanlı veri akışı eklenince |
| 6.2 | Celery task queue | 10+ paralel kullanıcı olunca |
| 6.3 | WebSocket canlı fiyat akışı | Kullanıcılar anlık fiyat isteyince |
| 6.4 | Eğitim modülü (finansal terimler sözlüğü, yatırım 101) | Platform büyüyünce |
| 6.5 | PWA mobil desteği | Mobil kullanıcı talebi olunca |
| 6.6 | Vektör DB (geçmiş rapor semantik arama) | 1000+ rapor olunca |
| 6.7 | Topluluk özellikleri (paylaşım, yorum) | Kullanıcı tabanı büyüyünce |

---

## 7. RİSKLER VE AZALTMA

| Risk | Olasılık | Etki | Azaltma |
|------|---------|------|---------|
| yfinance rate limit / breaking change | Yüksek | Orta | Çoklu veri sağlayıcı fallback zinciri (Aşama 3.8) |
| Yahoo Finance tamamen kapanır | Düşük | Yüksek | Alpha Vantage + Finnhub geçiş planı hazır |
| LLM API maliyeti artar | Orta | Orta | Ollama yerel LLM her zaman yedek |
| SEC EDGAR/Finnhub API değişiklikleri | Orta | Düşük | Fallback mekanizmaları |
| Kod karmaşıklığı artar | Orta | Orta | Her aşamada refactor + temizlik |
| Teknik borç birikir | Orta | Yüksek | Her 2 aşamada bir code-review + cleanup |

---

## ÖZET ZAMAN ÇİZELGESİ

```
Aşama 1 [2-3 hafta]  ████████░░░░░░░░░░░░  Temel güçlendirme
Aşama 2 [3-4 hafta]  ░░░░░░░░████████░░░░  LLM + Chat arayüzü
Aşama 3 [3-4 hafta]  ░░░░░░░░░░░░░██████░░  Veri + PostgreSQL
Aşama 4 [4-5 hafta]  ░░░░░░░░░░░░░░░░░████  Backtest + Grafik
Aşama 5 [4-6 hafta]  ░░░░░░░░░░░░░░░░░████  Expert katmanı
Aşama 6 [sürekli]     ░░░░░░░░░░░░░░░░░░░░  Olgunluk

TOPLAM: ~16-22 hafta (4-5.5 ay) ana geliştirme
```

---

> **İlke:** "Basit ama işlevsel." Önce çalışan minimumu sağlamlaştır, sonra derinleştir.  
> Her aşamada terminal teması korunur, kod temiz ve anlaşılır kalır.  
> Tamamen açık kaynak ve ücretsiz araçlarla.
