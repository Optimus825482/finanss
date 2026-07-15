"""yf_utils retry wrapper testleri (network çağrısı yapılmaz — mock ile)."""
from unittest.mock import patch, MagicMock
import pytest

import yfinance
from app.services.yf_utils import with_retry, safe_ticker_info, safe_ticker_news, safe_download


class TestWithRetry:
    def test_succeeds_first_try(self):
        fn = MagicMock(return_value=42)
        assert with_retry(fn) == 42
        assert fn.call_count == 1

    def test_retries_on_failure(self):
        fn = MagicMock(side_effect=[Exception("fail"), Exception("fail"), 99])
        assert with_retry(fn, retries=3, backoff_base=0.01) == 99
        assert fn.call_count == 3

    def test_raises_after_max_retries(self):
        fn = MagicMock(side_effect=Exception("always fail"))
        with pytest.raises(Exception, match="always fail"):
            with_retry(fn, retries=2, backoff_base=0.01)
        assert fn.call_count == 2


class TestSafeWrappers:
    def test_safe_ticker_info_returns_dict_on_failure(self):
        with patch.object(yfinance, "Ticker", side_effect=Exception("network")):
            result = safe_ticker_info("AAPL", retries=1)
            assert result == {}

    def test_safe_ticker_news_returns_empty_list_on_failure(self):
        with patch.object(yfinance, "Ticker", side_effect=Exception("network")):
            result = safe_ticker_news("AAPL", retries=1)
            assert result == []

    def test_safe_download_returns_none_on_failure(self):
        with patch.object(yfinance, "download", side_effect=Exception("network")):
            result = safe_download(["AAPL"], retries=1)
            assert result is None
