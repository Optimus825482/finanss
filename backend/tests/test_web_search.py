"""web_search pure parser testleri — DDG/Google News/Reddit/HN parse + dedup."""
from datetime import datetime, timezone

from app.services.web_search import (
    SearchHit,
    _dedupe_hits,
    _parse_ddg_html,
    _parse_google_news_rss,
    _parse_hn_json,
    _parse_reddit_json,
)


# --- DuckDuckGo HTML parser ---

DDG_SAMPLE = """
<div class="results">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa">AAPL earnings beat</a>
  <a class="result__snippet">Apple beat Q3 estimates</a>
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fb">MSFT upgrade</a>
  <a class="result__snippet" style="display:none">Microsoft raised target</a>
</div>
"""


class TestParseDDG:
    def test_extracts_results(self):
        hits = _parse_ddg_html(DDG_SAMPLE, "AAPL")
        assert len(hits) == 2
        assert hits[0].title == "AAPL earnings beat"
        assert "example.com/a" in hits[0].link
        assert hits[0].source_provider == "ddg"

    def test_empty_html(self):
        assert _parse_ddg_html("", "x") == []
        assert _parse_ddg_html("no results here", "x") == []

    def test_url_redirect_decoded(self):
        hits = _parse_ddg_html(DDG_SAMPLE, "x")
        # uddg= URL encoded → decoded olmalı
        assert "%2F" not in hits[0].link  # encode çözülmüş


# --- Google News RSS parser ---

GOOGLE_NEWS_SAMPLE = """<?xml version="1.0"?>
<rss>
  <channel>
    <item>
      <title><![CDATA[AAPL hits new high]]></title>
      <link>https://news.google.com/articles/abc123</link>
      <pubDate>Mon, 15 Jul 2026 10:30:00 GMT</pubDate>
      <source url="https://bloomberg.com">Bloomberg</source>
    </item>
    <item>
      <title>MSFT downgrade</title>
      <link>https://news.google.com/articles/xyz</link>
      <pubDate>Tue, 16 Jul 2026 14:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


class TestParseGoogleNews:
    def test_extracts_items(self):
        hits = _parse_google_news_rss(GOOGLE_NEWS_SAMPLE, "AAPL")
        assert len(hits) == 2
        assert hits[0].title == "AAPL hits new high"
        assert hits[0].publisher == "Bloomberg"
        assert hits[0].timestamp is not None  # RFC822 parsed
        assert hits[1].publisher == "google_news"  # source tag yoksa default

    def test_empty_rss(self):
        assert _parse_google_news_rss("<rss></rss>", "x") == []


# --- Reddit JSON parser ---

REDDIT_SAMPLE = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "AAPL discussion",
                    "permalink": "/r/investing/comments/abc/aapl_discussion/",
                    "subreddit": "investing",
                    "created_utc": 1721044800,
                }
            },
            {
                "data": {
                    "title": "MSFT news",
                    "permalink": "/r/stocks/comments/def/msft_news/",
                    "subreddit": "stocks",
                    "created_utc": 1721131200,
                }
            },
        ]
    }
}


class TestParseReddit:
    def test_extracts_posts(self):
        hits = _parse_reddit_json(REDDIT_SAMPLE)
        assert len(hits) == 2
        assert hits[0].title == "AAPL discussion"
        assert hits[0].publisher == "r/investing"
        assert "reddit.com" in hits[0].link
        assert hits[0].timestamp == 1721044800

    def test_missing_title_skipped(self):
        data = {"data": {"children": [{"data": {"permalink": "/x"}}]}}
        assert _parse_reddit_json(data) == []

    def test_missing_permalink_skipped(self):
        data = {"data": {"children": [{"data": {"title": "x"}}]}}
        assert _parse_reddit_json(data) == []


# --- Hacker News parser ---

HN_SAMPLE = {
    "hits": [
        {
            "title": "Show HN: stock analysis tool",
            "url": "https://example.com/tool",
            "created_at_i": 1721044800,
            "objectID": "12345",
        },
        {
            "story_title": "AAPL acquisition rumor",
            "url": None,  # url yoksa HN discussion linki
            "objectID": "67890",
            "created_at": 1721131200,
        },
    ]
}


class TestParseHN:
    def test_extracts_stories(self):
        hits = _parse_hn_json(HN_SAMPLE)
        assert len(hits) == 2
        assert hits[0].title == "Show HN: stock analysis tool"
        assert hits[0].link == "https://example.com/tool"
        assert hits[0].timestamp == 1721044800

    def test_url_fallback_to_hn_discussion(self):
        hits = _parse_hn_json(HN_SAMPLE)
        # ikinci hit'te url None → HN discussion linki
        assert "news.ycombinator.com/item?id=67890" in hits[1].link

    def test_empty(self):
        assert _parse_hn_json({"hits": []}) == []


# --- Dedup ---

class TestDedupeHits:
    def test_empty(self):
        assert _dedupe_hits([]) == []

    def test_unique_kept(self):
        hits = [
            SearchHit("A", "p1", "u1", 100, "ddg"),
            SearchHit("B", "p2", "u2", 200, "google_news"),
        ]
        out = _dedupe_hits(hits)
        assert len(out) == 2

    def test_duplicate_title_collapsed(self):
        hits = [
            SearchHit("Same title", "p1", "u1", 100, "ddg"),
            SearchHit("same  title", "p2", "u2", 200, "reddit"),  # whitespace normalize
        ]
        out = _dedupe_hits(hits)
        assert len(out) == 1
        # daha yüksek timestamp kazanır
        assert out[0].timestamp == 200

    def test_case_insensitive(self):
        hits = [
            SearchHit("AAPL News", "p", "u1", 100, "ddg"),
            SearchHit("aapl news", "p", "u2", 200, "google_news"),
        ]
        assert len(_dedupe_hits(hits)) == 1

    def test_keep_newer_when_duplicate(self):
        hits = [
            SearchHit("X", "p1", "u1", 50, "ddg"),
            SearchHit("X", "p2", "u2", 150, "hn"),  # daha yeni
        ]
        out = _dedupe_hits(hits)
        assert len(out) == 1
        assert out[0].timestamp == 150


# --- SearchHit.to_rumor_format ---

class TestRumorFormat:
    def test_maps_fields(self):
        h = SearchHit(
            title="AAPL news",
            publisher="bloomberg",
            link="https://x.com/a",
            timestamp=1721044800,
            source_provider="google_news",
        )
        out = h.to_rumor_format()
        assert out["title"] == "AAPL news"
        assert out["publisher"] == "bloomberg"
        assert out["link"] == "https://x.com/a"
        assert out["providerPublishTime"] == 1721044800
