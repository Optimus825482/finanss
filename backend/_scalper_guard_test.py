# Guard davranışı self-check — execute_buy/sell mantığını simüle eder.
# ponytail: DB'ye yazmadan mantık doğrulaması; gerçek integrasyon backend upken.
import json


def buy_guard_blocks(open_tickers: set, sym: str) -> bool:
    """execute_buy guard'ı: açık pozisyon varsa engelle."""
    return sym in open_tickers


def sell_guard_blocks(status: str) -> bool:
    """execute_sell guard'ı: open değilse engelle."""
    return status != "open"


def realized_pl_roundtrip(pl: float) -> float:
    """factors JSON round-trip."""
    return json.loads(json.dumps({"realized_pl": pl}))["realized_pl"]


# buy guard: aynı ticker 2x alım engellendi
open_tickers = {"DOGEUSDT", "SOLUSDT"}
assert buy_guard_blocks(open_tickers, "DOGEUSDT") is True, "zaten açık ticker engellenmeli"
assert buy_guard_blocks(open_tickers, "ETHUSDT") is False, "yeni ticker serbest"
assert buy_guard_blocks(set(), "DOGEUSDT") is False, "açık poz yokken serbest"

# sell guard: kapalı pozisyon tekrar satılamaz
assert sell_guard_blocks("closed") is True, "kapalı pozisyon tekrar satılamaz"
assert sell_guard_blocks("open") is False, "açık pozisyon satılabilir"

# realized_pl round-trip
assert realized_pl_roundtrip(-0.05) == -0.05, "pl korunmalı"
assert realized_pl_roundtrip(None) is None, "None korunmalı"

print("ALL GUARD TESTS PASSED")
