"""Anahtarsız ücretsiz web search — 4 sağlayıcı.

Kaynaklar (hiçbiri API anahtarı gerektirmez):
- DuckDuckGo HTML — genel arama (https://html.duckduckgo.com/html/?q=...)
- Google News RSS — haber akışı (https://news.google.com/rss/search?q=...)
- Reddit JSON — sosyal tartışma (https://www.reddit.com/search.json?q=...)
- Hacker News Algolia — teknoloji (https://hn.algolia.com/api/v1/search?query=...)

Tüm sonuçlar birleştirilip rumor_scanner formatına map edilir:
  {"title", "publisher", "link", "providerPublishTime" (unix epoch)}

httpx async + User-Agent header. Rate limit yok (sayfa scrape olduğu için nazik ol).
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Genel User-Agent — bazı sağlayıcılar botblock için ister
_UA = (
    "Mozilla/5.0 (compatible; OrbisFinaiSkill/1.0; +https://github.com/orbis-finai)"
)
_DEFAULT_TIMEOUT = 20.0


@dataclass
class SearchHit:
    """Birleştirilmiş arama sonucu — rumor_scanner'a beslemek için."""
    title: str
    publisher: Optional[str]
    link: str
    timestamp: Optional[int]  # unix epoch saniye
    source_provider: str  # "ddg" | "google_news" | "reddit" | "hn"

    def to_rumor_format(self) -> dict:
        """rumor_scanner'ın beklediği yfinance news formatına map."""
        return {
            "title": self.title,
            "publisher": self.publisher,
            "link": self.link,
            "providerPublishTime": self.timestamp,
        }


# --- DuckDuckGo HTML scrape ---

_DDG_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_DDG_REDIRECT_RE = re.compile(r"uddg=([^&\"']+)")
_DDG_SNIPPET_RE = re.compile(
    r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(html: str) -> str:
    """HTML etiketlerini soy + entity'leri decode et."""
    import html as html_lib
    text = _TAG_RE.sub("", html)
    return html_lib.unescape(text).strip()


def _parse_ddg_html(html: str, query: str) -> list[SearchHit]:
    """DuckDuckGo HTML sonucunu parse et. Test edilebilir pure fonksiyon."""
    hits: list[SearchHit] = []
    for m in _DDG_RESULT_RE.finditer(html):
        raw_url = m.group(1)
        # DuckDuckGo redirect URL'ini decode et
        redirect = _DDG_REDIRECT_RE.search(raw_url)
        if redirect:
            try:
                from urllib.parse import unquote
                url = unquote(redirect.group(1))
            except Exception:
                url = raw_url
        else:
            url = raw_url
        title = _strip_tags(m.group(2))
        if not title or not url:
            continue
        hits.append(SearchHit(
            title=title,
            publisher="duckduckgo",
            link=url,
            timestamp=None,
            source_provider="ddg",
        ))
    return hits


async def _fetch_ddg(query: str, limit: int = 10) -> list[SearchHit]:
    """DuckDuckGo HTML'den arama."""
    if not query:
        return []
    try:
        async with httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT, follow_redirects=True, headers={"User-Agent": _UA}
        ) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "b": ""},  # POST en güvenilir
            )
            resp.raise_for_status()
            return _parse_ddg_html(resp.text, query)[:limit]
    except Exception as e:
        logger.warning("web_search DDG failed (%s): %s", query, e)
        return []


# --- Google News RSS ---

def _parse_google_news_rss(xml: str, query: str) -> list[SearchHit]:
    """Google News RSS XML'ini parse. Test edilebilir pure fonksiyon.

    RSS item: <item><title>...</title><link>...</link><pubDate>...</pubDate></item>
    """
    hits: list[SearchHit] = []
    items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
    for item in items[:20]:
        title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", item, re.DOTALL)
        link_m = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
        pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item, re.DOTALL)
        source_m = re.search(r"<source[^>]*>(.*?)</source>", item, re.DOTALL)

        title = None
        if title_m:
            title = title_m.group(1) or title_m.group(2)
        if not title:
            continue

        link = link_m.group(1).strip() if link_m else ""
        publisher = source_m.group(1).strip() if source_m else "google_news"

        ts = None
        if pub_m:
            ts = _parse_rfc822(pub_m.group(1).strip())

        hits.append(SearchHit(
            title=_strip_tags(title),
            publisher=publisher,
            link=link,
            timestamp=ts,
            source_provider="google_news",
        ))
    return hits


def _parse_rfc822(date_str: str) -> Optional[int]:
    """RFC 822 tarih (RSS pubDate) → unix epoch. Hata → None."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


async def _fetch_google_news(query: str, limit: int = 10) -> list[SearchHit]:
    """Google News RSS'den arama."""
    if not query:
        return []
    try:
        async with httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT, headers={"User-Agent": _UA}
        ) as client:
            url = f"https://news.google.com/rss/search?q={query}+when:7d&hl=en-US&gl=US&ceid=US:en"
            resp = await client.get(url)
            resp.raise_for_status()
            return _parse_google_news_rss(resp.text, query)[:limit]
    except Exception as e:
        logger.warning("web_search Google News failed (%s): %s", query, e)
        return []


# --- Reddit JSON ---

def _parse_reddit_json(data: dict) -> list[SearchHit]:
    """Reddit search.json çıktısını parse. Test edilebilir pure fonksiyon."""
    hits: list[SearchHit] = []
    try:
        children = data.get("data", {}).get("children", [])
        for child in children[:20]:
            cdata = child.get("data", {})
            title = cdata.get("title")
            permalink = cdata.get("permalink")
            subreddit = cdata.get("subreddit")
            created = cdata.get("created_utc")
            if not title or not permalink:
                continue
            hits.append(SearchHit(
                title=title,
                publisher=f"r/{subreddit}" if subreddit else "reddit",
                link=f"https://www.reddit.com{permalink}",
                timestamp=int(created) if created else None,
                source_provider="reddit",
            ))
    except Exception as e:
        logger.warning("web_search Reddit parse failed: %s", e)
    return hits


async def _fetch_reddit(query: str, limit: int = 10) -> list[SearchHit]:
    """Reddit search.json'dan arama (anahtarsız)."""
    if not query:
        return []
    try:
        async with httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT, headers={"User-Agent": _UA}
        ) as client:
            url = f"https://www.reddit.com/search.json?q={query}&limit={limit}&sort=relevance&t=week"
            resp = await client.get(url)
            resp.raise_for_status()
            return _parse_reddit_json(resp.json())
    except Exception as e:
        logger.warning("web_search Reddit failed (%s): %s", query, e)
        return []


# --- Hacker News Algolia ---

def _parse_hn_json(data: dict) -> list[SearchHit]:
    """HN Algolia API çıktısını parse. Test edilebilir pure fonksiyon."""
    hits: list[SearchHit] = []
    try:
        for hit in data.get("hits", [])[:20]:
            title = hit.get("title") or hit.get("story_title") or hit.get("comment_text")
            if not title:
                continue
            # url yoksa HN discussion linki
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            ts = hit.get("created_at_i") or hit.get("created_at")
            hits.append(SearchHit(
                title=_strip_tags(title)[:300],
                publisher="hacker_news",
                link=url,
                timestamp=ts,
                source_provider="hn",
            ))
    except Exception as e:
        logger.warning("web_search HN parse failed: %s", e)
    return hits


async def _fetch_hn(query: str, limit: int = 10) -> list[SearchHit]:
    """Hacker News Algolia API'den arama."""
    if not query:
        return []
    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            url = (
                "https://hn.algolia.com/api/v1/search"
                f"?query={query}&tags=story&hitsPerPage={limit}"
            )
            resp = await client.get(url)
            resp.raise_for_status()
            return _parse_hn_json(resp.json())
    except Exception as e:
        logger.warning("web_search HN failed (%s): %s", query, e)
        return []


# --- Birleştirilmiş fetch ---

DEFAULT_SOURCES = ("ddg", "google_news", "reddit", "hn")

_PROVIDERS = {
    "ddg": _fetch_ddg,
    "google_news": _fetch_google_news,
    "reddit": _fetch_reddit,
    "hn": _fetch_hn,
}


def _dedupe_hits(hits: list[SearchHit], now: Optional[datetime] = None) -> list[SearchHit]:
    """Aynı başlık + url + 7gün pencere dedup. Test edilebilir pure fonksiyon."""
    if not hits:
        return []
    now = now or datetime.now(timezone.utc)
    seen: dict[str, SearchHit] = {}
    for h in hits:
        key = re.sub(r"\s+", " ", h.title.lower()).strip()
        if not key:
            continue
        existing = seen.get(key)
        if existing is None:
            seen[key] = h
        elif h.timestamp and (existing.timestamp is None or h.timestamp > existing.timestamp):
            seen[key] = h
    return list(seen.values())


async def search(
    query: str,
    sources: tuple[str, ...] = DEFAULT_SOURCES,
    limit_per_source: int = 10,
) -> list[SearchHit]:
    """Çok kaynaklı web arama. Tüm sağlayıcıları paralel çağırır.

    Args:
        query: arama sorgusu (ticker veya şirket adı)
        sources: hangi sağlayıcılar ("ddg", "google_news", "reddit", "hn")
        limit_per_source: her sağlayıcıdan max sonuç

    Returns:
        Birleştirilmiş + dedup edilmiş SearchHit listesi
    """
    if not query:
        return []

    tasks = []
    for src in sources:
        provider = _PROVIDERS.get(src)
        if provider is None:
            logger.warning("web_search: bilinmeyen kaynak %s, atlanıyor", src)
            continue
        tasks.append(provider(query, limit_per_source))

    if not tasks:
        return []

    results_nested = await asyncio.gather(*tasks, return_exceptions=True)
    all_hits: list[SearchHit] = []
    for result in results_nested:
        if isinstance(result, Exception):
            logger.warning("web_search provider error: %s", result)
            continue
        if isinstance(result, list):
            all_hits.extend(result)

    return _dedupe_hits(all_hits)


async def fetch_rumor_format(
    query: str,
    sources: tuple[str, ...] = DEFAULT_SOURCES,
    limit_per_source: int = 10,
) -> list[dict]:
    """Rumor scanner için haber formatında sonuçlar döndürür.

    yfinance `.news` formatıyla align: {title, publisher, link, providerPublishTime}
    """
    hits = await search(query, sources=sources, limit_per_source=limit_per_source)
    return [h.to_rumor_format() for h in hits]
