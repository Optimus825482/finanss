# ORBIS FINAI — Güvenlik Denetim Raporu

**Tarih:** 2026-08-02 · **Kapsam:** `backend/app/` (28 servis, 17 router, middleware, models) + frontend auth akışı
**Yöntem:** Satır-satır statik inceleme. Seviye: Kritik / Yüksek / Orta / Düşük.
**Not:** Bu rapor, takılan güvenlik agent'ı yerine koordinatörün kendi incelemesi + önceki oturumdaki dove/security-analyst bulgularıyla birleştirilmiştir.

---

## 1. Kritik

### S1. FERNET_KEY yoksa LLM API key'leri DB'de düz metin
`backend/app/models/llm.py:13-22` (`_get_fernet`), `:45-64` (`set/get_decrypted_api_key`)

- `_get_fernet()` yalnızca `FERNET_KEY` env var'ı setse cipher döner; yoksa `None`.
- `set_encrypted_api_key()` fernet yoksa **raw string saklar**; `get_decrypted_api_key()` fernet yoksa **raw döner**.
- Docker compose'ta `FERNET_KEY: ${FERNET_KEY:-}` — boşsa (varsayılan) **şifreleme yok**.
- Etki: DB erişimi olan herkes (dump, backup, admin DB) tüm LLM provider API key'lerini okuyabilir.

**Düzeltme:**
1. `startup`'ta `FERNET_KEY` yoksa uyarı logla (tercihen fail).
2. `create_provider`'da fernet yoksa provider kaydını reddet veya açıkça "şifresiz" işaretle.
3. Önerilen: `.env.example`'da FERNET_KEY zorunlu yap.

### S2. Tek paylaşımlı API key — kullanıcı/auth yok
`backend/app/middleware.py:28`

- Tüm uçlar tek `API_KEY` env var'ıyla korunuyor. Kullanıcı bazlı auth, session, JWT, MFA yok.
- Admin uçları (`/api/admin/*`) dahil **her şey aynı key'e güveniyor**.
- `PUBLIC_PATHS = ("/api/status", "/docs", "/openapi.json", "/redoc")` — `/docs` + `/openapi.json` açık → API şeması public (bilgi sızıntısı düşük ama mevcut).

**Düzeltme:** Multi-user planlanana kadar: (a) prod'da `API_KEY` zorunlu + en az 32 karakter; (b) admin uçları için ikinci key veya `X-Admin-Key`; (c) `/docs`'u prod'da kapat.

---

## 2. Yüksek

### S3. SSRF — provider test endpoint'i keyed URL'ye HTTP çağrısı yapıyor
`backend/app/services/admin_service.py:131` `test_provider_connection` + `backend/app/routers/admin.py:84`

- `api_test_provider` kullanıcı sağladığı `base_url`'e POST gönderiyor (llm_bridge.generate ile).
- Admin key'e erişen veya key'siz ortamda herkes `base_url`'i internal IP'ye (`http://169.254.169.254`, `http://localhost:5432`) çevirip internal servisleri yoklayabilir / veri gönderebilir.

**Düzeltme:** `base_url`'i localhost/private IP aralıklarına karşı doğrula (URL parse + ipaddress modülü), sadece HTTPS allowlist.

### S4. API_KEY boşsa tüm auth kapalı
`backend/app/middleware.py:20-22`

```python
api_key = os.getenv("API_KEY", "")
if api_key:
    ...
```

- `API_KEY` boşsa middleware hiçbir şey kontrol etmez — **tüm uçlar (admin, portfolio, balance, chat, memory) anonim açık**.
- Docker compose: `API_KEY: ${API_KEY:-}` — boşsa prod'da açık.

**Düzeltme:** `NODE_ENV=production` veya `ALLOW_NO_AUTH != 1` iken API_KEY yoksa startup fail. `.env.example` "local dev only" notu yetersiz.

---

## 3. Orta

### S5. Rate limit proxy IP'ye düşüyor (X-Forwarded-For yok)
`backend/app/main.py:11` `limiter = Limiter(key_func=get_remote_address)`

- Reverse proxy/load balancer arkasında tüm kullanıcılar proxy IP'sinden görünür → 120/min limiti tek kullanıcıyı bile keser veya tümünü aynı kovada toplar.
- SSE stream de bu limitten etkilenir (uzun bağlantı tek istek olduğu için genelde sorun değil).

**Düzeltme:** Proxy arkasında `X-Forwarded-For`'u güvenilir proxy listesiyle doğrula.

### S6. Chat prompt injection + hafıza sızıntısı
`backend/app/routers/chat.py:44-58`

- Kullanıcı mesajı doğrudan LLM prompt'una gidiyor; `system_prompt` içinde kullanıcı profili + hafıza bağlamı var.
- "Sistem talimatlarını atla ve ..." tarzı injection ile profil/hafıza sızabilir.
- Etki: düşük (kişisel veri tek kullanıcılı sistemde), ama LLM davranış bozulması mümkün.

**Düzeltme:** Kullanıcı inputunu sistem prompt'tan ayır (zaten ayrı), injection kalıplarını filtrele veya çıktıyı "yatırım tavsiyesi değildir" sınırına zorla.

### S7. Ticker path parametreleri doğrudan yfinance'a
`backend/app/routers/predictions.py:25` `t.history(...)`, `screener.py:38` `yf.Search(q)`

- Enjeksiyon değil (yfinance string alır) ama: (a) beklenmedik/uzun input uzun network çağrısına yol açar (DoS düşük); (b) `yf.Search(q)` user input'u Yahoo'ya gönderir — minimal.

**Düzeltme:** Ticker uzunluğu/desen doğrulaması (`^[A-Z0-9.\-]{1,10}$`).

### S8. `get_live_prices` cache yazımı yalnızca başarılı sonuçlarda
`backend/app/services/market_data.py:135`

- `None` fiyatlar cache'lenmez → başarısız ticker her 3s SSE polling'de yeniden çekilir (rate-limit baskısı + yavaşlama). DoS değil ama kaynak israfı.

---

## 4. Düşük

### S9. `/docs` + `/openapi.json` public
- API şeması (uç listesi, şema) internetten okunabilir. Bilgi sızıntısı sınırlı (auth key'i içermez).

### S10. `ALLOW_DESTRUCTIVE_RESET` env var'ı kullanılmıyor
`backend/.env.example:24` tanımlı ama `middleware.py`'de okunmuyor — her zaman `X-Confirm-Reset: yes` ister (güvenli taraf, ama env ölü kod).

### S11. LLM bridge'de timeout/retry yok
`backend/app/services/llm_bridge.py:147` `await litellm.acompletion` — provider yavaşsa pipeline asılı kalır.

---

## 5. Pozitif Bulgular

| Kontrol | Durum |
|---------|-------|
| `_safe_compare` constant-time (length-safe `compare_digest`) | ✅ |
| CORS sabit allowlist (2 origin), `allow_credentials=True` | ✅ |
| slowapi 120/min tüm API | ✅ |
| `eval` / `shell` / `pickle` / `yaml.load` sıfır kullanım | ✅ |
| SQLAlchemy parametreize (SQL injection yüzeyi yok) | ✅ |
| Destructive reset `X-Confirm-Reset: yes` header guard | ✅ |
| `secrets.compare_digest` ile length eşitliği ön kontrol | ✅ |
| API key header `X-API-Key` (cookie değil) | ✅ |
| Webhook opsiyonel + never-raise | ✅ |
| Fernet şifreleme altyapısı mevcut (S1'de devreye girmiyor) | ✅ altyapı |

---

## 6. Öncelikli Aksiyon

| Öncelik | Aksiyon | Referans |
|---------|---------|----------|
| 🔴 P1 | FERNET_KEY zorunlu yap; fernet yoksa provider kaydını reddet | S1 |
| 🔴 P1 | API_KEY boşsa prod'da startup fail | S4 |
| 🟠 P2 | Provider test `base_url`'ine SSRF doğrulaması | S3 |
| 🟠 P2 | Admin uçlarına ikinci key | S2 |
| 🟡 P3 | X-Forwarded-For rate-limit düzeltmesi | S5 |
| 🟡 P3 | Ticker input doğrulaması | S7 |
| 🟢 P4 | `/docs` prod kapat · `ALLOW_DESTRUCTIVE_RESET` temizle · LLM timeout | S9/S10/S11 |
