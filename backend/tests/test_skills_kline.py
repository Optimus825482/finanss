"""K-line chart pattern detection testleri — pure fonksiyon, matplotlib bağımsız."""
from app.skills.kline_chart import detect_pattern


class TestDoji:
    def test_doji_small_body(self):
        # Gövde = 0.1, aralık = 5 → 0.1/5 = 2% < 5%
        assert detect_pattern(open_=100, high=105, low=100, close=100.1) == "doji"

    def test_not_doji_large_body(self):
        # Gövde 5, aralık 5 → 100% > 5%
        assert detect_pattern(open_=100, high=105, low=100, close=105) != "doji"


class TestHammer:
    def test_hammer_lower_shadow_dominant(self):
        # open=100, close=101 (body=1), low=95 (lower_shadow=5), high=101.5 (upper=0.5)
        # lower_shadow 5 ≥ 2*body=2 ✓, upper 0.5 < body*0.5=0.5 → false (eşit)
        # threshold: < 0.5 tam eşit — ama 0.49 olsun
        assert detect_pattern(open_=100, high=101.4, low=95, close=101) == "hammer"

    def test_not_hammer_no_lower_shadow(self):
        # open=100, close=110 (body=10), low=100, high=110
        # lower_shadow=0 → not hammer
        assert detect_pattern(open_=100, high=110, low=100, close=110) != "hammer"


class TestEngulfingBullish:
    def test_bullish_engulfing(self):
        # Önceki bearish: open=110, close=100 (düşüş)
        # Mevcut bullish: open=99, close=115 (yükseliş), gövde 16 > 10
        # close(115) >= prev_open(110) ✓, open(99) <= prev_close(100) ✓
        assert detect_pattern(
            open_=99, high=116, low=98, close=115,
            prev_open=110, prev_close=100,
        ) == "engulfing_bullish"

    def test_not_engulfing_same_direction(self):
        # Önceki de bullish → engulfing değil
        assert detect_pattern(
            open_=100, high=110, low=99, close=109,
            prev_open=100, prev_close=105,
        ) != "engulfing_bullish"


class TestEngulfingBearish:
    def test_bearish_engulfing(self):
        # Önceki bullish: open=100, close=110
        # Mevcut bearish: open=111, close=95, gövde 16 > 10
        # close(95) <= prev_open(100) ✓, open(111) >= prev_close(110) ✓
        assert detect_pattern(
            open_=111, high=112, low=94, close=95,
            prev_open=100, prev_close=110,
        ) == "engulfing_bearish"


class TestEdgeCases:
    def test_none_values_return_none_str(self):
        assert detect_pattern(open_=None, high=10, low=5, close=8) == "none"

    def test_zero_range_returns_none(self):
        # high=low → rng=0 → none
        assert detect_pattern(open_=5, high=5, low=5, close=5) == "none"

    def test_no_pattern_returns_none_str(self):
        # Normal mum, pattern yok
        assert detect_pattern(open_=10, high=12, low=9, close=11) == "none"
