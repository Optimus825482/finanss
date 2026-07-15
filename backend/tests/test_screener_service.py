"""Screener service universe + exchange fonksiyonları için testler (network gerektirmez)."""
from app.services.screener_service import get_universe, list_exchanges


class TestGetUniverse:
    def test_all_universe(self):
        tickers = get_universe()
        assert len(tickers) > 100  # toplam evren > 100 hisse
        assert "AAPL" in tickers
        assert "AKBNK.IS" in tickers

    def test_specific_exchange(self):
        tickers = get_universe(["BIST"])
        assert "AKBNK.IS" in tickers
        assert "AAPL" not in tickers  # BIST'te AAPL yok

    def test_multiple_exchanges(self):
        tickers = get_universe(["NASDAQ", "BIST"])
        assert "AAPL" in tickers
        assert "THYAO.IS" in tickers

    def test_no_duplicates(self):
        """get_universe dedup yapar — hiç ticker iki kez çıkmamalı."""
        tickers = get_universe()
        assert len(tickers) == len(set(tickers))

    def test_empty_input(self):
        tickers = get_universe(None)
        assert len(tickers) > 0

    def test_invalid_exchange_skipped(self):
        tickers = get_universe(["NASDAQ", "FAKE_EXCHANGE"])
        assert "AAPL" in tickers
        # FAKE_EXCHANGE silently skipped


class TestListExchanges:
    def test_returns_all_exchanges(self):
        exchanges = list_exchanges()
        slugs = [e["slug"] for e in exchanges]
        assert "NASDAQ" in slugs
        assert "BIST" in slugs
        assert "LSE" in slugs
        assert "Euronext" in slugs

    def test_has_ticker_count(self):
        exchanges = list_exchanges()
        for e in exchanges:
            assert e["ticker_count"] > 0
            assert e["label"]  # label boş değil
