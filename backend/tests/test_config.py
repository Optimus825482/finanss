"""Config değerleri ve tutarlılık testleri."""
from app.config import (
    STOCK_UNIVERSE, BENCHMARK_TICKER, SCORING_WEIGHTS,
    TOP_N_PICKS, SCHEDULE_HOUR, SCHEDULE_MINUTE, TIMEZONE,
)


class TestStockUniverse:
    def test_all_exchanges_populated(self):
        for slug, tickers in STOCK_UNIVERSE.items():
            assert len(tickers) > 5, f"{slug} çok az ticker"

    def test_bist_has_is_suffix(self):
        for t in STOCK_UNIVERSE["BIST"]:
            assert t.endswith(".IS"), f"BIST ticker {t} .IS ile bitmiyor"

    def test_no_cross_exchange_duplicates(self):
        """Aynı ticker iki borsada olmamalı (cross-list hariç).
        DOWJONES index olduğu için NYSE ile çakışması normaldir."""
        seen = {}
        for slug, tickers in STOCK_UNIVERSE.items():
            for t in tickers:
                if t in seen and seen[t] != slug:
                    # Allow DOWJONES overlap (index constituents trade on NYSE/NASDAQ)
                    if slug == "DOWJONES" or seen[t] == "DOWJONES":
                        continue
                    assert False, f"{t} hem {seen[t]} hem {slug} içinde"
                seen[t] = slug

    def test_bist_no_duplicates(self):
        tickers = STOCK_UNIVERSE["BIST"]
        assert len(tickers) == len(set(tickers)), "BIST içinde mükerrer ticker"

    def test_nyse_no_duplicates(self):
        tickers = STOCK_UNIVERSE["NYSE"]
        assert len(tickers) == len(set(tickers)), "NYSE içinde mükerrer ticker"


class TestConfig:
    def test_scoring_weights_sum_to_one(self):
        total = sum(SCORING_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01, f"Ağırlık toplamı {total}, 1.0 olmalı"

    def test_benchmark_is_sp500(self):
        assert BENCHMARK_TICKER == "^GSPC"

    def test_top_n_positive(self):
        assert TOP_N_PICKS > 0

    def test_schedule_8am_istanbul(self):
        assert SCHEDULE_HOUR == 8
        assert SCHEDULE_MINUTE == 0
        assert TIMEZONE == "Europe/Istanbul"
