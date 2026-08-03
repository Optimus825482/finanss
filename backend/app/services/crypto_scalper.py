"""Crypto Scalper - 24/7 otonom scalping döngüsü (kripto).

Modül seviyesinde tek `asyncio.Task` + `asyncio.Event`:
- `start()`: idempotent - zaten çalışıyorsa aynı görevi döndürür.
- `stop()`: event set → döngü bir sonraki tick'te kapanır.
- `status()`: durum + son tur bilgisi (frontend 1s polling).

Her tur:
1. Universe tara (get_price + CryptoAgent MT sinyali).
2. Açık pozisyonlara stop / take-profit / zayıf sinyal çıkışı.
3. Yeni sinyal (composite ≥ eşik) → sabit bütçe ile alım
   (AutonomousAgent.execute_buy - bakiye + karar loglama).
4. 1 saniye bekle. Kripto 7/24 - piyasa saati kontrolü yok.
"""
import asyncio
import logging
import threading
import time
from datetime import datetime

from app.config import CRYPTO_UNIVERSE, PORTFOLIOS
from app.database import SessionLocal
from app.models.core import PortfolioPosition
from app.models.portfolio import Portfolio
from app.services.binance_service import get_price, get_klines

logger = logging.getLogger(__name__)

# ── Parametreler ──
SCAN_INTERVAL_S = 1.0
BUY_THRESHOLD = 65.0       # composite ≥ bu → alım
STOP_LOSS_PCT = 0.015      # -%1.5 → stop
TAKE_PROFIT_PCT = 0.025    # +%2.5 → k-r al
# Eşzamanlı açık pozisyon limiti — PORTFOLIOS["crypto"].max_positions'dan çekilir
# (tek doğruluk kaynağı). Fallback 3.
MAX_OPEN_POSITIONS = int(PORTFOLIOS.get("crypto", {}).get("max_positions", 3))
POSITION_USD = 25.0        # pozisyon başına bütçe (USDT)
MIN_SIGNAL_DROP = 55.0     # açık poz: sinyal < bu → çık

# ── Modül state ──
_stop_event: asyncio.Event | None = None
_thread: threading.Thread | None = None          # stop() thread'in bitmesini beklesin
_last_signals: dict[str, dict] | None = None  # son tarama sonucu (cards için)
_state: dict = {
    "running": False,
    "started_at": None,
    "stopped_at": None,
    "last_round_at": None,
    "last_round": None,
    "rounds": 0,
}


def _set_state(**kw):
    _state.update(kw)


def status() -> dict:
    """Döngü durumu + son tur bilgisi."""
    return dict(_state)


def is_running() -> bool:
    return bool(_state.get("running"))


def cards() -> dict:
    """Kural bazlı AL/HOLD/SELL kartları - frontend 1s polling.

    Sinyaller scalper döngüsünün son taramasından okunur (`_last_signals`);
    böylece her poll Binance'e tekrar vurmaz, scalper ile çakışmaz.
    Scalper kapalıysa (veya daha ilk tarama yapılmadıysa) fallback olarak
    kendi taramasını yapar.

    Kural sonucu doğrudan scalper parametrelerinden türetilir:
      - Açık poz: STOP-LOSS / TAKE-PROFIT / sinyal<MIN_SIGNAL_DROP → SELL (nedenli)
      - Açık poz: diğer → HOLD
      - Açık yok: composite≥BUY_THRESHOLD → BUY (AL adayı)
      - Açık yok: diğer → BEKLE
    """
    global _last_signals
    db = SessionLocal()
    try:
        from app.services.autonomous_agent import AutonomousAgent
        agent = AutonomousAgent(portfolio_slug="crypto")
        portfolio_id = agent._ensure_portfolio_id(db)
        open_pos = {p.ticker: p for p in _open_positions(db, portfolio_id)}
        signals = _last_signals
        if not signals:
            signals = _crypto_signals(CRYPTO_UNIVERSE)
            _last_signals = signals
        cards_out: list[dict] = []
        for sym, sig in signals.items():
            price = sig.get("price") or 0
            composite = sig.get("composite", 50)
            pos = open_pos.get(sym)
            rule = None
            action = "hold"
            if pos and price > 0 and pos.entry_price:
                pnl_pct = (price - pos.entry_price) / pos.entry_price
                if pnl_pct <= -STOP_LOSS_PCT:
                    action, rule = "sell", f"STOP-LOSS {pnl_pct*100:.2f}%"
                elif pnl_pct >= TAKE_PROFIT_PCT:
                    action, rule = "sell", f"TAKE-PROFIT {pnl_pct*100:.2f}%"
                elif composite < MIN_SIGNAL_DROP:
                    action, rule = "sell", f"sinyal zayıf (composite {composite:.0f})"
                else:
                    action, rule = "hold", f"HOLD - stop {STOP_LOSS_PCT*100:.1f}% / TP {TAKE_PROFIT_PCT*100:.1f}%"
            elif pos:
                action, rule = "hold", "HOLD - pozisyon var"
            elif composite >= BUY_THRESHOLD:
                action, rule = "buy", f"AL adayı - composite {composite:.0f} ≥ {BUY_THRESHOLD:.0f}"
            else:
                action, rule = "wait", f"bekle - composite {composite:.0f} < {BUY_THRESHOLD:.0f}"

            card = {
                "ticker": sym,
                "price": price,
                "composite": float(composite),
                "rsi": sig.get("rsi"),
                "momentum_5m": sig.get("momentum_5m"),
                "momentum_15m": sig.get("momentum_15m"),
                "momentum_1h": sig.get("momentum_1h"),
                "action": action,
                "rule": rule,
            }
            if pos:
                pnl = ((price - pos.entry_price) / pos.entry_price * 100) if pos.entry_price else 0
                card.update({
                    "position_open": True,
                    "position_qty": pos.quantity,
                    "entry_price": pos.entry_price,
                    "pnl_pct": round(pnl, 2),
                })
            else:
                card.update({"position_open": False, "position_qty": 0, "entry_price": None, "pnl_pct": None})
            # numpy skalerleri JSON'a gitmez - normalize
            for k, v in card.items():
                if isinstance(v, (float, int)) and not isinstance(v, bool):
                    card[k] = float(v)
            cards_out.append(card)

        cards_out.sort(key=lambda c: (c["action"] != "buy", -c["composite"]))
        return {
            "running": is_running(),
            "status": status(),
            "cards": cards_out,
            "params": {
                "buy_threshold": BUY_THRESHOLD,
                "stop_loss_pct": STOP_LOSS_PCT * 100,
                "take_profit_pct": TAKE_PROFIT_PCT * 100,
                "max_open_positions": MAX_OPEN_POSITIONS,
                "position_usd": POSITION_USD,
                "min_signal_drop": MIN_SIGNAL_DROP,
                "scan_interval_s": SCAN_INTERVAL_S,
            },
        }
    finally:
        db.close()


def start() -> dict:
    """Scalper döngüsünü başlat - idempotent.

    FastAPI senkron endpoint'i thread pool'da çalıştığı için burada
    event loop yoktur; `asyncio.create_task` doğrudan çalışmaz.
    Kendi event loop'lu arka plan thread'i açılır.
    """
    global _stop_event, _thread
    if is_running():
        return status()
    _stop_event = asyncio.Event()
    _set_state(running=True, started_at=datetime.now().isoformat(), stopped_at=None)

    def _run_loop():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_loop())
        except Exception:
            logger.exception("crypto_scalper döngü hatası")
        finally:
            _set_state(running=False, stopped_at=datetime.now().isoformat())
            logger.info("crypto_scalper: thread kapandı")

    _thread = threading.Thread(target=_run_loop, name="crypto-scalper", daemon=True)
    _thread.start()
    logger.info("crypto_scalper: başlatıldı")
    return status()


def stop(timeout: float = 10.0) -> dict:
    """Scalper döngüsünü durdur (mevcut tur biter) ve thread'in bitmesini bekle.

    `timeout` — in-flight `_tick` 15 sembol × 3 timeframe tarayabildiği için
    makul bir üst sınır verir; thread bitmezse daemon olduğu için süreçle gider.
    """
    global _stop_event, _thread
    if is_running() and _stop_event is not None:
        _stop_event.set()
    if _thread is not None and _thread.is_alive():
        _thread.join(timeout)
    return status()


# ── Yardımcılar ──

def _crypto_signals(symbols: list[str]) -> dict[str, dict]:
    """Evren için MT sinyal haritası: {sym: {price, composite, momentum_5m, rsi, ...}}."""
    from app.agents.crypto_agent import compute_crypto_signal_mt
    out: dict[str, dict] = {}
    for sym in symbols:
        px = get_price(sym)
        if not px:
            continue
        klines_by_tf = {}
        for tf in ("5m", "15m", "1h"):
            klines_by_tf[tf] = get_klines(sym, tf, limit=100) or []
        if not any(klines_by_tf.values()):
            continue
        sig = compute_crypto_signal_mt(klines_by_tf)
        # numpy skalerleri JSON'a gitmez - float'a normalize et
        sig = {k: (float(v) if isinstance(v, (float, int)) and not isinstance(v, bool) else v)
               for k, v in sig.items()}
        out[sym] = {"price": float(px["price"]), **sig}
    return out


def _open_positions(db, portfolio_id: int) -> list[PortfolioPosition]:
    return (db.query(PortfolioPosition)
            .filter(PortfolioPosition.status == "open")
            .filter(PortfolioPosition.portfolio_id == portfolio_id)
            .all())


# ── Ana döngü ──

async def _loop():
    global _stop_event
    ev = _stop_event
    db = SessionLocal()
    try:
        while ev is not None and not ev.is_set():
            try:
                await asyncio.to_thread(_tick, db)
            except Exception as e:
                logger.exception("crypto_scalper tick hatası: %s", e)
                # Zehirlenmiş session'ı temizle — sonraki tick'lerin commit'i çalışsın.
                db.rollback()
            _set_state(rounds=_state.get("rounds", 0) + 1)
            await asyncio.sleep(SCAN_INTERVAL_S)
    finally:
        db.close()
        _set_state(running=False, stopped_at=datetime.now().isoformat())
        logger.info("crypto_scalper: durduruldu")


def _tick(db):
    """Tek tur: sinyaller → açık poz yönetimi → yeni alımlar."""
    global _last_signals
    from app.services.autonomous_agent import AutonomousAgent
    round_start = time.time()

    # Önceki tick'ten kalan başarısız transaction varsa temizle (güvenli no-op).
    db.rollback()

    agent = AutonomousAgent(portfolio_slug="crypto")
    portfolio_id = agent._ensure_portfolio_id(db)
    portfolio_before = agent.get_portfolio(db)

    signals = _crypto_signals(CRYPTO_UNIVERSE)
    _last_signals = signals  # cards() aynı veriyi kullansın
    if not signals:
        _set_state(last_round_at=datetime.now().isoformat(),
                   last_round={"ok": False, "error": "fiyat alınamadı",
                               "ms": int((time.time() - round_start) * 1000)})
        return

    actions: list[dict] = []

    # ── Açık pozisyon yönetimi (stop / T-P / zayıf sinyal) ──
    for pos in _open_positions(db, portfolio_id):
        px = get_price(pos.ticker)
        price = (px or {}).get("price") or 0
        if not price:
            # get_price başarısız — bu turdaki sinyal fiyatını dene; o da yoksa atla ama sessiz kalma.
            price = (signals.get(pos.ticker) or {}).get("price") or 0
        if not price:
            logger.warning("scalper: %s fiyat alınamadı — pozisyon yönetilmedi (stop-loss riski)", pos.ticker)
            continue
        sig = signals.get(pos.ticker)
        entry = pos.entry_price or 0
        pnl_pct = (price - entry) / entry if entry else 0
        reason = None
        if pnl_pct <= -STOP_LOSS_PCT:
            reason = f"STOP-LOSS {pnl_pct*100:.2f}%"
        elif pnl_pct >= TAKE_PROFIT_PCT:
            reason = f"TAKE-PROFIT {pnl_pct*100:.2f}%"
        elif sig and sig.get("composite", 50) < MIN_SIGNAL_DROP:
            reason = f"sinyal zayıf (composite {sig['composite']:.0f})"
        if reason:
            try:
                result = agent.execute_sell(db, pos.id, price, f"scalper: {reason}", portfolio_before, confidence=0.8)
                if result.get("success"):
                    actions.append({"action": "sell", "ticker": pos.ticker,
                                    "price": price, "reason": reason,
                                    "pnl_pct": round(pnl_pct * 100, 2),
                                    "pl": result.get("pl")})
            except Exception as e:
                logger.exception("scalper: %s satış hatası: %s", pos.ticker, e)
                db.rollback()

    # ── Yeni alımlar ──
    open_positions = _open_positions(db, portfolio_id)
    open_tickers = {p.ticker for p in open_positions}
    if len(open_positions) < MAX_OPEN_POSITIONS:
        ranked = sorted(signals.items(),
                        key=lambda kv: kv[1].get("composite", 50), reverse=True)
        for sym, sig in ranked:
            if len(_open_positions(db, portfolio_id)) >= MAX_OPEN_POSITIONS:
                break
            if sym in open_tickers:
                continue  # zaten açık — ticker bazlı tekrar alım yok
            if sig.get("composite", 50) < BUY_THRESHOLD:
                continue
            price = sig.get("price") or 0
            if price <= 0:
                continue
            qty = round(POSITION_USD / price, 6)
            if qty <= 0:
                continue
            reasoning = (f"scalper sinyal composite={sig['composite']:.1f} "
                         f"rsi={sig.get('rsi', 50):.0f} "
                         f"mom5m={sig.get('momentum_5m', 50):.0f} "
                         f"mom15m={sig.get('momentum_15m', 50):.0f} "
                         f"mom1h={sig.get('momentum_1h', 50):.0f}")
            try:
                result = agent.execute_buy(db, sym, qty, price, reasoning, portfolio_before, confidence=0.8)
                if result.get("success"):
                    actions.append({"action": "buy", "ticker": sym, "price": price,
                                    "quantity": qty, "composite": sig["composite"],
                                    "rsi": sig.get("rsi"), "momentum_5m": sig.get("momentum_5m"),
                                    "momentum_15m": sig.get("momentum_15m"),
                                    "momentum_1h": sig.get("momentum_1h")})
            except Exception as e:
                logger.exception("scalper: %s alım hatası: %s", sym, e)
                db.rollback()

    # İşlemlerden sonra taze cash oku — bu turdaki al/sat yansımış olsun.
    _portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    _cash = _portfolio.cash if _portfolio else 0.0
    _set_state(last_round_at=datetime.now().isoformat(),
               last_round={
                   "ok": True,
                   "scanned": len(signals),
                   "open_positions": len(_open_positions(db, portfolio_id)),
                   "actions": actions,
                   # Equity = nakit + açık poz market değeri. Önceki sürüm sadece
                   # açık poz değerini sayıyordu → kapanan pozların kâr/zararı
                   # toplam portföyü değiştirmiyor görünüyordu.
                   "equity_usdt": round(_cash + sum(
                       (signals.get(p.ticker) or {}).get("price", p.entry_price or 0) * p.quantity
                       for p in _open_positions(db, portfolio_id)), 2),
                   "ms": int((time.time() - round_start) * 1000),
                   "timestamp": datetime.now().isoformat(),
               })
