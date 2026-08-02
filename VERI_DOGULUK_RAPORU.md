# ORBIS FINAI — Veri Doğruluğu & Finansal Motor Analizi

**Tarih:** 2026-08-02 · **Kapsam:** skorlama, fair value, prediction, risk, sinyal motorları
**Yöntem:** Formül doğrulaması + test çıktıları + statik inceleme. Etki: Para kaybı / Sinyal bozulması / Düşük.

---

## 1. KRİTİK: Peter Lynch Fair Value formülü sistematik PEG sapması üretir

`backend/app/services/fair_value.py:22-35`

```python
def peter_lynch_fair_value(eps, eps_growth_pct, dividend_yield_pct=0):
    ratio = eps_growth_pct + dividend_yield_pct   # ör: 15 + 3 = 18
    fair = eps * ratio if ratio > 0 else eps * 15
    peg = (fair / eps) / growth if growth > 0 else 99   # = ratio/growth = 18/15 = 1.2
```

**Sorun 1 — PEG hesaplaması:** `peg = (fair/eps)/growth = (growth+div)/growth = 1 + div/growth`. Temettü verimi PEG'e dahil edilmemeli. Standart PEG = PE / growth. Sonuç: temettü ödeyen hisselerde PEG her zaman >1 → **sistematik "pahalı" görünüm** (Lynch modeli temettüyü ayrı değerler, PEG'i bozmaz).

**Sorun 2 — Lynch'in temettü düzeltmesi:** Lynch'in orijinal PEG yaklaşımında temettü verimi growth'a eklenir (`PEG = PE / (growth + yield)` değil — Lynch "growth + yield" oranını kullanır ama **PE'yi böler**, fair value = EPS × (growth+yield) şeklinde değil). Bu implementasyonda `fair = eps × (growth+yield)` — bu, PE_implied = growth+yield yapar, yani fair value growth+yield çarpanlı. Bu, "fair = EPS × growth" (yaygın) veya "fair = EPS × (growth + yield)" (Lynch'e yakın) arasında belirsiz. **Formül dokümantasyonu + PEG mantığı çelişkili.**

**Somut örnek:**
- EPS=2.00, growth=15%, div=3%, fiyat=30
- Bu kod: fair = 2 × 18 = **36**, PEG = 18/15 = **1.2**
- Beklenen (Lynch PE/growth): PE = 15, PEG = **1.0**, fair ≈ 30 (adil)
- Sonuç: hisse "iskontolu" (%20 marj) görünür — oysa adil fiyatlandırılmış.

**Etki:** **Sinyal bozulması** — fair value ensemble'ında Lynch ağırlığı 0.20 (satır 114), "düşük değerli" yanlış pozitifleri artırır.

**Düzeltme:**
```python
# Lynch PEG-uyumlu: PEG = PE / (growth + yield); fair = EPS * (growth + yield) KABUL ediliyorsa
# PEG'i ayrı hesapla, fair'ı etkilemesin:
peg = eps_growth_pct and (ratio / eps_growth_pct) if eps_growth_pct else None
# VEYA temettüyü PEG'den çıkar:
peg = (fair / eps) / growth  # growth>0 ise; div'ı dahil etme
```

---

## 2. YÜKSEK: Prediction engine — XGBoost `n_jobs=-1` + her çağrıda retrain (CPU starvation)

`backend/app/services/prediction_engine.py:505-511,552-563`

- Her `create_prediction` 3 horizon × `XGBRegressor(n_estimators=100, n_jobs=-1)` **tüm CPU çekirdeklerini** kullanır.
- Model cache YOK — `_has_model` var ama `create_prediction` içinde train'i atlamıyor; disk model dosyası (`data/models/*.json`) yalnızca `predict`'te yükleniyor.
- 8 hisse analizi = 24 XGBoost fit. SSE + diğer ajanlar starvation.

**Etki:** Yüksek — canlı sistemde diğer istekler gecikir; `_run_deep`'te pick başına 30-90s.

**Düzeltme (hızlı kazanım #1):**
```python
# create_prediction içinde, train öncesi:
if not all(XGBoostPredictor._has_model(t.upper(), h) for h in XGBoostPredictor.HORIZONS):
    XGBoostPredictor.train(...)
# model dosyası mtime < 24h ise de atla
```

---

## 3. YÜKSEK: Ensemble fair value — outlier model koruması yetersiz

`backend/app/services/fair_value.py:107-127` `ensemble_fair_value`

- `use = [v for v in valid if 0.05*price < v < 5*price]` — 5× fiyat üstü DCF (yüksek büyüme varsayımı) dahil edilir; 0.05× altı (sermaye yoğun) dışlanır.
- `len(use) < 2` ise `use = valid` — **outlier koruması atlanır**.
- Ağırlıklar iki kez tanımlı (satır 109 sonra 114 override) — ilk blok ölü kod.
- DCF terminal growth `wacc - terminal_growth` böleni: `wacc=0.09, terminal=0.025` → 0.065 OK. Ama `growth_rate` yüksek gelirse (örn. 0.30) terminal değer patlar — `growth_rate` `earningsGrowth`'tan geliyor, yüzde/ondalık karışıklığı `fair_value.py:146-149`'da normalize ediliyor ama `growth>1` ise %100+ olarak kabul ediliyor.

**Etki:** Orta — DCF uç değerleri ensemble'ı saptırabilir.

---

## 4. YÜKSEK: `autonomous_agent._gather_candidates` naive/aware datetime — DÜZELTİLDİ

`backend/app/services/autonomous_agent.py:357` (commit 8c5f474)

- `datetime.now()` (naive) vs `Report.created_at = now_istanbul()` (UTC+3 aware) → `TypeError: can't subtract offset-naive and offset-aware` riski + yanlış rapor yaşı → yanlış rapor tetikleme kararı.
- **Düzeltildi:** ikisi de UTC naive'ye normalize edildi (8c5f474).
- Etki (düzeltme öncesi): 30dk turunda rapor yaşı yanlış hesaplanır, gereksiz pipeline tetikleme veya eski rapor kullanımı → **sinyal bozulması**.

---

## 5. ORTA: Composite skor — risk_inverse formülü doğru ama edge case'ler

`backend/app/agents/report_agent.py:151` + `orchestrator.py:113`

```python
composite = fundamental*0.40 + sentiment*0.30 + (100-risk)*0.30
```

- Doğru: yüksek risk → düşük katkı. ✓
- Edge: `risk_score` NaN ise `sanitize_float(pick["risk_score"], 50.0)` persist'te 50'ye düşer ama `_compose` içinde NaN kalabilir → `(100-NaN)=NaN` → composite NaN → `sort` bozulur. Stage 2'de risk hep set ediliyor ama `safe_ticker_history` boşsa `risk_score=50.0` (risk_agent.py:38) — genelde güvenli.
- **Risk:** `risk_agent` benchmark alınamazsa `beta=None` → `beta_component=50` → risk skoru 50'ye yaklaşır — nötr sapma kabul edilebilir.

---

## 6. ORTA: Bull/Bear consensus — normalize mantığı

`backend/app/agents/research_team.py:21-55`

- `consensus = (bull - bear + 100) / 2` — 0-100 scale ✓.
- `_bull_case`/`_bear_case`: `raw = score / reasons`, sonra `max(10, min(95, raw))` — ama `raw` zaten 0-100 değil: başlangıç 50.0 + bonuslar (örn. +35+30+25+20+15+10+20 = 205) / 7 reasons = ~29.3. **Bu 0-100'e sıkıştırılmıyor** — `max(10, min(95, 29.3))` = 29.3. Yani bull skor 50 baz + bonuslarla bile 95'i nadiren aşar, ortalama ~30-40 kalır. Konsensüs `(bull - bear + 100)/2` — bull ~30, bear ~30 ise konsensüs ~50 nötr. Ama güçlü bull adayda bull ~40, bear ~60 olabilir → konsensüs 40 → "bearish" — **skorların absolute değeri yanıltıcı** (relative fark önemli).
- **Etki:** Düşük-orta — konsensüs relative okunmalı; absolute 0-100 skor olarak sunuluyor.

---

## 7. ORTA: SentimentAgent VADER-only

`backend/app/agents/sentiment_agent.py:29`

- VADER genel İngilizce duygu sözlüğü — finansal jargon ("beat", "upgrade", "buyback", "lawsuit") yanlış skorlanır.
- `(avg+1)*50` — tek haber bile skoru 50'den uzaklaştırır; haber yoksa 50 nötr.
- **Etki:** Sinyal gürültüsü — NewsAnalyst (burst+trend+event) kullanılmıyor.

---

## 8. ORTA: RSI hesabı — yeni veri eksikse avg_loss=1.0 fallback

`backend/app/services/screener_service.py` (stage1) + `prediction_engine.py`

- `avg_loss = mean(losses[-14:]) if len >= 14 else 1.0` — veri <14 günse RSI 50 civarı sabitlenir (yanlış).
- `rsi = 100 - 100/(1 + avg_gain/avg_loss)` — `avg_loss=0` (tamamen yükselen) ise RSI=100 (aşırı alım) — doğru.
- **Etki:** Düşük — stage1 zaten 20+ gün ister.

---

## 9. DÜŞÜK: `detect_volume_anomaly` VPT bug — DÜZELTİLDİ

`backend/app/services/alpha_generator.py:58` (commit 7247b60)

- `np.cumsum(Series)[-1]` label-based `KeyError: -1` → fonksiyon her çağrıda exception → `smart_money_signal: "error"`.
- **Düzeltildi:** `np.asarray` eklendi. Etki (öncesi): smart money sinyali asla çalışmıyordu, otonom ajan `composite ±3/±5` bonuslarını alamıyordu — **sessiz sinyal kaybı**.

---

## 10. DÜŞÜK: Piotroski — prev_info yoksa kriterler "iyimser" varsayar

`backend/app/services/piotroski.py:83,97,109,131` — `prev_info` yokken "no dilution assume ok", "debt < 100 = olumlu", "gross margin > 0.2 = olumlu", "asset turnover > 0.5 = olumlu" — veri yokken skor şişebilir.

---

## 11. DÜŞÜK: `fair_value.py:136` wrapper'sız `yf.Ticker().info`

- Retry/backoff yok — rate-limit'te anında fail, fair value sessiz düşer.

---

## 12. Pozitif Doğrulamalar

| Kontrol | Sonuç |
|---------|-------|
| Graham Number `sqrt(22.5*EPS*BVPS)` | ✅ doğru |
| DCF `Σ FCF/(1+WACC)^t + TV/(1+WACC)^n`, TV = FCF(1+g)/(WACC-g) | ✅ doğru |
| P/E karşılaştırması `EPS × sektör_ortalama_PE` | ✅ doğru |
| Composite `f×0.40 + s×0.30 + (100-r)×0.30` | ✅ doğru |
| Risk `vol×0.45 + dd×0.35 + beta×0.20` | ✅ doğru |
| Kelly `W - (1-W)/R`, half-Kelly bounds 1%-25% | ✅ doğru |
| Backtest `run_buy_hold` / `run_signal_backtest` | ✅ test edildi, doğru |
| HMM 2-state Gaussian forward + adaptif ağırlık | ✅ doğru |
| Bull/Bear consensus relative okuma | ⚠️ absolute scale yanıltıcı (Bölüm 6) |

---

## 13. Öncelikli Aksiyon

| Öncelik | Aksiyon | Referans |
|---------|---------|----------|
| 🔴 P1 | Peter Lynch PEG/formül tutarlılığı (div yield'i PEG'e katma) | Bölüm 1 |
| 🔴 P1 | XGBoost günlük train gate + `n_jobs` sınırla | Bölüm 2 |
| 🟠 P2 | Ensemble outlier koruması + ölü ağırlık bloğu temizliği | Bölüm 3 |
| 🟠 P2 | Bull/bear skorlarını 0-100'e gerçek normalize et | Bölüm 6 |
| 🟡 P3 | NewsAnalyst'i sentiment'e entegre et (VADER sığ) | Bölüm 7 |
| 🟡 P3 | `fair_value.py`'de `safe_ticker_info` kullan | Bölüm 11 |
