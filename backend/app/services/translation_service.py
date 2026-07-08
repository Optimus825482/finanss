"""
Türkçe çeviri servisi.

Katmanlar:
1. Statik haritalar — sektör, ülke, borsa isimleri (ücretsiz, anlık)
2. LLM çeviri — açıklama, haber başlıkları (PostgreSQL cache'li)
3. Fallback — LLM yoksa/başarısızsa orijinal metin
"""
import hashlib
import asyncio
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TranslationCache

# ── Statik Çeviri Haritaları ──

SECTOR_TR: dict[str, str] = {
    "Technology": "Teknoloji",
    "Consumer Electronics": "Tüketici Elektroniği",
    "Software—Application": "Yazılım",
    "Software - Application": "Yazılım",
    "Software—Infrastructure": "Yazılım Altyapısı",
    "Semiconductors": "Yarı İletkenler",
    "Financial Services": "Finansal Hizmetler",
    "Banks—Diversified": "Bankacılık",
    "Banks - Diversified": "Bankacılık",
    "Banks—Regional": "Bölgesel Bankacılık",
    "Insurance": "Sigortacılık",
    "Healthcare": "Sağlık",
    "Biotechnology": "Biyoteknoloji",
    "Drug Manufacturers": "İlaç Sanayi",
    "Medical Devices": "Tıbbi Cihazlar",
    "Energy": "Enerji",
    "Oil & Gas": "Petrol & Gaz",
    "Consumer Cyclical": "Tüketici Döngüsel",
    "Consumer Defensive": "Tüketici Savunma",
    "Retail": "Perakende",
    "Industrials": "Endüstriyel",
    "Aerospace & Defense": "Havacılık & Savunma",
    "Transportation": "Ulaştırma",
    "Real Estate": "Gayrimenkul",
    "Utilities": "Elektrik/Su/Doğalgaz",
    "Communication Services": "İletişim Hizmetleri",
    "Basic Materials": "Temel Malzemeler",
    "Building Materials": "Yapı Malzemeleri",
    "Chemicals": "Kimya",
    "Metals & Mining": "Metal & Madencilik",
    "Telecom": "Telekomünikasyon",
    "Media": "Medya",
    "Entertainment": "Eğlence",
    "Automotive": "Otomotiv",
    "Food & Beverage": "Gıda & İçecek",
    "Apparel": "Giyim",
    "Hotel & Travel": "Otel & Seyahat",
    "Airline": "Havayolu",
    "Restaurants": "Restoranlar",
}

COUNTRY_TR: dict[str, str] = {
    "United States": "ABD",
    "United Kingdom": "Birleşik Krallık",
    "Germany": "Almanya",
    "France": "Fransa",
    "Japan": "Japonya",
    "China": "Çin",
    "Switzerland": "İsviçre",
    "Netherlands": "Hollanda",
    "Canada": "Kanada",
    "South Korea": "Güney Kore",
    "Taiwan": "Tayvan",
    "Turkey": "Türkiye",
    "Brazil": "Brezilya",
    "India": "Hindistan",
    "Hong Kong": "Hong Kong",
    "Spain": "İspanya",
    "Italy": "İtalya",
    "Sweden": "İsveç",
    "Denmark": "Danimarka",
    "Finland": "Finlandiya",
    "Norway": "Norveç",
    "Belgium": "Belçika",
    "Austria": "Avusturya",
    "Portugal": "Portekiz",
    "Australia": "Avustralya",
    "Saudi Arabia": "Suudi Arabistan",
}

EXCHANGE_NAME_TR: dict[str, str] = {
    "NasdaqGS": "NASDAQ",
    "NasdaqGM": "NASDAQ GM",
    "NasdaqCM": "NASDAQ CM",
    "Nasdaq": "NASDAQ",
    "NYSE": "NYSE",
    "NYSE American": "NYSE American",
    "BIST": "BIST",
    "London": "Londra Borsası",
    "Tokyo": "Tokyo Borsası",
    "Hong Kong": "Hong Kong Borsası",
    "Shanghai": "Şanghay Borsası",
    "Shenzhen": "Shenzhen Borsası",
    "Euronext": "Euronext",
    "SIX": "İsviçre Borsası",
    "TSX": "Toronto Borsası",
    "B3": "Brezilya Borsası",
    "BME": "Madrid Borsası",
    "Oslo": "Oslo Borsası",
    "Vienna": "Viyana Borsası",
    "Milan": "Milano Borsası",
}


def translate_sector(sector_en: str) -> str:
    """Sektör ismini Türkçe'ye çevir."""
    if not sector_en:
        return ""
    # Birebir eşleşme
    if sector_en in SECTOR_TR:
        return SECTOR_TR[sector_en]
    # Kısmi eşleşme (örn: "Technology" içinde "Technology" varsa)
    for en, tr in SECTOR_TR.items():
        if en.lower() in sector_en.lower():
            return tr
    return sector_en


def translate_country(country_en: str) -> str:
    """Ülke ismini Türkçe'ye çevir."""
    if not country_en:
        return ""
    return COUNTRY_TR.get(country_en, country_en)


def translate_exchange(exchange_en: str) -> str:
    """Borsa ismini Türkçe'ye çevir."""
    if not exchange_en:
        return ""
    return EXCHANGE_NAME_TR.get(exchange_en, exchange_en)


def translate_financial_field(field_name: str) -> str:
    """Finansal metrik alan adını Türkçe'ye çevir."""
    mapping = {
        "Market Cap": "Piyasa Değeri",
        "P/E Ratio": "F/K Oranı",
        "PEG Ratio": "PEG Oranı",
        "P/B Ratio": "Piyasa/Defter",
        "EPS": "Hisse Başı Kazanç",
        "ROE": "Özsermaye Karlılığı",
        "Dividend Yield": "Temettü Verimi",
        "Revenue Growth": "Gelir Büyümesi",
        "Debt/Equity": "Borç/Özsermaye",
        "Beta": "Beta",
        "52W High": "52 Hafta Yüksek",
        "52W Low": "52 Hafta Düşük",
        "50-Day Avg": "50 Gün Ort.",
        "200-Day Avg": "200 Gün Ort.",
        "Employees": "Çalışanlar",
        "Volume": "Hacim",
        "Avg Volume": "Ort. Hacim",
        "Open": "Açılış",
        "Previous Close": "Önceki Kapanış",
        "Day High": "Gün Yüksek",
        "Day Low": "Gün Düşük",
    }
    return mapping.get(field_name, field_name)


# ── LLM Tabanlı Dinamik Çeviri (cache'li) ──

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _cached_translate(db: Session, text: str, target_lang: str = "tr") -> Optional[str]:
    """Önbellekten çeviri getir."""
    h = _hash_text(text)
    cached = db.query(TranslationCache).filter(
        TranslationCache.source_hash == h,
        TranslationCache.target_lang == target_lang,
    ).first()
    if cached:
        cached.hit_count += 1
        db.commit()
        return cached.translated_text
    return None


def _cache_translation(db: Session, text: str, translated: str, target_lang: str = "tr"):
    """Çeviriyi önbelleğe kaydet."""
    h = _hash_text(text)
    existing = db.query(TranslationCache).filter(
        TranslationCache.source_hash == h,
        TranslationCache.target_lang == target_lang,
    ).first()
    if existing:
        existing.hit_count += 1
        return

    entry = TranslationCache(
        source_hash=h,
        source_text=text[:500],
        target_lang=target_lang,
        translated_text=translated,
    )
    db.add(entry)
    db.commit()


async def translate_text(text: str, target_lang: str = "tr", use_llm: bool = True) -> str:
    """Metni çevir. Önce cache, sonra LLM (admin'de yapılandırılmış provider ile), fallback orijinal."""
    if not text or not text.strip():
        return text

    db = SessionLocal()
    try:
        # 1. Cache kontrol
        cached = _cached_translate(db, text, target_lang)
        if cached:
            return cached

        # 2. LLM çeviri — admin panelde yapılandırılmış provider/model kullan
        translated = text  # fallback: orijinal

        if use_llm:
            try:
                from app.services.admin_service import get_translation_config
                from app.models import LLMProvider
                from openai import OpenAI

                config = get_translation_config(db)
                if config.get("has_api_key") and config.get("base_url") and config.get("model_name"):
                    # Get real API key from provider record (not exposed via config)
                    provider = db.query(LLMProvider).filter(LLMProvider.id == config["provider_id"]).first()
                    if not provider or not provider.api_key:
                        config = None
                    else:
                        config["api_key"] = provider.api_key  # internal use only
                else:
                    config = None

                if config:
                    client = OpenAI(base_url=config["base_url"], api_key=config["api_key"])
                    prompt = f"""Aşağıdaki finansal metni Türkçe'ye çevir.
Sadece çeviriyi ver, açıklama ekleme. Finansal terimleri doğru çevir.
Metin: {text[:2000]}"""

                    resp = client.chat.completions.create(
                        model=config["model_name"],
                        messages=[
                            {"role": "system", "content": "Sen profesyonel bir finans çevirmenisin. İngilizce'den Türkçe'ye birebir ve doğru çeviri yap. Sadece çeviriyi ver."},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                        max_tokens=min(config.get("max_tokens", 1024), 1024),
                    )
                    result = resp.choices[0].message.content
                    if result and len(result.strip()) > 10:
                        translated = result.strip()
            except Exception:
                pass  # LLM başarısız, orijinal kalır

        # 3. Cache'e kaydet
        _cache_translation(db, text, translated, target_lang)
        return translated
    finally:
        db.close()


async def translate_batch(texts: list[str], target_lang: str = "tr") -> list[str]:
    """Birden çok metni paralel çevir."""
    if not texts:
        return []

    # Kısa metinleri tek prompt'ta çevir (daha hızlı, daha az API çağrısı)
    non_empty = [t for t in texts if t and t.strip()]
    if not non_empty:
        return texts

    # Önce cache'e bak
    db = SessionLocal()
    uncached = []
    results_map: dict[str, str] = {}

    try:
        for text in non_empty:
            cached = _cached_translate(db, text, target_lang)
            if cached:
                results_map[text] = cached
            else:
                uncached.append(text)

        # Cache'te olmayanları LLM ile çevir
        if uncached:
            try:
                from app.services.llm_bridge import generate

                for text in uncached:
                    translated = await translate_text(text, target_lang, use_llm=True)
                    results_map[text] = translated
            except Exception:
                for text in uncached:
                    results_map[text] = text

        return [results_map.get(t, t) for t in texts]
    finally:
        db.close()
