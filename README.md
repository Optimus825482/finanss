# ORBIS FINAI — ORBIS Finance Analyze Team

5 ajanlı bir AI araştırma ekibi (Tarama → Temel Analiz → Haber/Sentiment → Risk → Rapor)
her gün 08:00'de (Europe/Istanbul) otomatik çalışır, yfinance üzerinden uluslararası
hisse evrenini tarar ve bileşik skora göre sıralanmış bir günlük rapor üretir.
Next.js arayüzü pipeline'ı canlı izler ve manuel tetiklemeye izin verir.

## Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8012
```

İlk açılışta `backend/data/reports.db` (SQLite) otomatik oluşturulur.

## Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Arayüz http://localhost:3009 adresinde açılır, backend http://localhost:8012
üzerinde çalışmalı.

## Watchlist'i özelleştirme

`backend/app/config.py` içindeki `WATCHLIST` listesi ABD/Avrupa/Asya karışık
20+ sembol içerir. Ticker eklemek/çıkarmak için bu listeyi düzenle — yfinance
formatına uygun semboller kullan (`.DE`, `.T`, `.KS`, `.HK`, `.L` gibi borsa
uzantılarına dikkat et).

## Skor mantığı

- **Temel Analiz** (%40): F/K, özkaynak karlılığı, gelir büyümesi, borçluluk
- **Sentiment** (%30): son haber başlıklarının VADER duygu skoru
- **Risk** (%30, ters çevrilir): yıllıklandırılmış volatilite, maksimum düşüş, beta

Ağırlıklar `backend/app/config.py > SCORING_WEIGHTS` içinden değiştirilebilir.

## Notlar

- yfinance ücretsiz ama resmi olmayan bir Yahoo Finance istemcisi — ara sıra
  rate-limit veya eksik veri (özellikle bazı Asya/Avrupa sembollerinde) görülebilir.
  Agent'lar bu durumda o sembolü atlayıp devam eder, pipeline durmaz.
- Zamanlanmış görevi değiştirmek için `backend/app/config.py > SCHEDULE_HOUR/MINUTE`.
- Paid API'ye geçiş gerekirse (Alpha Vantage/Finnhub) sadece `scanner_agent.py`,
  `fundamental_agent.py` içindeki veri çekme kısımlarını değiştirmek yeterli;
  skorlama ve orchestrator mantığı aynı kalır.
