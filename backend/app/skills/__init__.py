"""stock_analysis skill port — 12 komut Python implementasyonu.

Kaynak skill: C:\\Users\\erkan\\.zcode\\skills\\stock-analysis-skill (Çince).
Port: Python, Türkçe çıktı, mevcut proje modüllerini yeniden kullanır.

Modüller:
- stock_analysis   — 个股分析 (zengin rapor + behavior rules + Fair Value + Prediction)
- dividend         — 股息分析 (safety/payout/CAGR/consecutive)
- rumor_scanner    — Haber Sinyal tarama (M&A/insider/analyst/regulatory/earnings, impact skor)
- kline_chart      — K线 (matplotlib + VLM pattern)
- sector_rotation  — Sektör Rotasyonu (relative strength, lider/geciken)
- correlation      — Korelasyon Matrisi (portföy çeşitlendirme)
- insider_activity — İçeriden İşlem (alım/satım dengesi)
- unusual_options  — Opsiyon Anomalileri (volume/OI, put/call)
- earnings_surprise— Bilanço Sürprizi (EPS tahmin vs gerçekleşen)
- seasonality      — Mevsimsellik (aylık/çeyreklik pattern'ler)
- fair_value_skill — Adil Değer (Graham/DCF/Lynch/PE + ensemble)
"""
