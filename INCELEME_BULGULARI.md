# İnceleme Bulguları

Tarih: 2026-08-02

## 1. jcode Context Window Algılama Hatası (ÇÖZÜLDÜ)

### Bulgu
- jcode, modelin gerçek context window'unu yanlış algılıyordu: model 1.000.000 token destekliyor ama jcode 200.000 olarak görüp sürekli compaction yapıyordu.
- Oturum ortasında gereksiz compact'lar context kaybına ve uzun bekleme sürelerine yol açıyordu.

### Kök Neden
- `C:\Users\erkan\.jcode\config.toml` içinde `[provider]` bölümünde:
  ```toml
  openai_native_compaction_threshold_tokens = 200000
  ```
- Bu eşik, native compaction'ı 200K token'da tetikliyordu.

### Yapılan Düzeltme
- Eşik 1.000.000'a yükseltildi (satır 112):
  ```toml
  openai_native_compaction_threshold_tokens = 1000000
  ```

### Durum
- ✅ Düzeltme uygulandı. Kalıcı etki için jcode restart gerekebilir.

## 2. Wigolo Kontrolü (ÇÖZÜLDÜ)

### Bulgu
- `wigolo doctor` çalıştırıldı → `status: ok`
- Config'de kayıtlı ve çalışır durumda.
- Başlangıçtaki şüphe çözüldü: Wigolo var, sorunsuz çalışıyor.

### Durum
- ✅ Kapandı.

## 3. jcode Repo ve Build Durumu

### Bulgu
- `selfdev find-config` → config: `C:\Users\erkan\.jcode\config.toml`
- Kaynak kod yerelde değil: **repository yok**, `selfdev setup` gerekir.
- Build kanalları:
  - `current` → yok (missing)
  - `stable` → var
  - `shared-server` → var
  - Build dizini: `C:\Users\erkan\AppData\Local\jcode\builds\`

### Not
- Repo olmadığı için kod değişikliği bu ortamda yapılamadı; düzeltme config üzerinden yapıldı.

## 4. Bekleyen Opsiyonel Temizlik
- [ ] `Remove-Item 'C:\Python313\Scripts\jcodemunch-mcp.exe.stale'` — eski .stale kalıntısı, istenirse silinebilir.

## 5. Oturum Sorunları (Gözlem)
- `mcp` ve `recall` tool çağrıları uzun sürdü / server reload ile kesildi (6-7 dk bekleme).
- `mcp__pmb-shared__recall` 385s sonra server reload nedeniyle iptal edildi.
- Bu, muhtemelen compaction/yeniden yükleme davranışıyla ilişkiliydi; düzeltme sonrası gözlemlenmeli.
