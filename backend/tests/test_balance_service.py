"""balance_service testleri — para hareketi katmanı (%0 coverage kapatır)."""
import pytest

from app.services.balance_service import (
    get_balance, deposit, withdraw, ensure_portfolio,
    record_position_opened, record_position_closed, reset_balance,
)
from app.models import VirtualBalance, BalanceTransaction, PortfolioPosition


class TestGetBalance:
    def test_creates_default_when_missing(self, db):
        bal = get_balance(db)
        db.commit()
        assert bal.cash == 100_000.0
        assert db.query(VirtualBalance).count() == 1

    def test_returns_existing(self, db):
        b1 = get_balance(db)
        db.commit()
        b2 = get_balance(db)
        assert b1.id == b2.id


class TestDepositWithdraw:
    def test_deposit_increases(self, db):
        bal = get_balance(db)
        before = bal.cash
        deposit(db, 500, "test")
        db.commit()
        assert bal.cash == before + 500
        tx = db.query(BalanceTransaction).filter(BalanceTransaction.type == "deposit").first()
        assert tx is not None and tx.amount == 500

    def test_withdraw_decreases(self, db):
        bal = get_balance(db)
        before = bal.cash
        withdraw(db, 250, "test")
        db.commit()
        assert bal.cash == before - 250

    def test_withdraw_insufficient_raises(self, db):
        get_balance(db)
        with pytest.raises(ValueError):
            withdraw(db, 10_000_000, "too much")


class TestEnsurePortfolio:
    def test_creates_bist(self, db):
        p = ensure_portfolio(db, "bist")
        db.commit()
        assert p.slug == "bist"
        assert p.cash == 50_000.0
        assert "BIST" in p.exchanges

    def test_creates_us(self, db):
        p = ensure_portfolio(db, "us")
        db.commit()
        assert p.slug == "us"
        assert p.cash == 10_000.0
        assert "NASDAQ" in p.exchanges

    def test_idempotent(self, db):
        p1 = ensure_portfolio(db, "bist")
        db.commit()
        p2 = ensure_portfolio(db, "bist")
        assert p1.id == p2.id

    def test_unknown_slug_raises(self, db):
        with pytest.raises(ValueError):
            ensure_portfolio(db, "mars")


class TestPositionAccounting:
    def _make_position(self, db, portfolio_id, ticker="AAPL", qty=10, price=100.0):
        pos = PortfolioPosition(
            ticker=ticker, quantity=qty, entry_price=price,
            status="open", portfolio_id=portfolio_id,
        )
        db.add(pos)
        db.flush()
        return pos

    def test_open_deducts_cash(self, db):
        p = ensure_portfolio(db, "bist")
        db.commit()
        before = p.cash
        pos = self._make_position(db, p.id)
        record_position_opened(db, pos.id, 1000.0, "AAPL", portfolio_id=p.id)
        db.commit()
        assert p.cash == before - 1000
        tx = db.query(BalanceTransaction).filter(
            BalanceTransaction.type == "transfer_out",
            BalanceTransaction.portfolio_id == p.id,
        ).first()
        assert tx is not None and tx.amount == 1000

    def test_close_adds_cash(self, db):
        p = ensure_portfolio(db, "bist")
        db.commit()
        before = p.cash
        pos = self._make_position(db, p.id)
        record_position_opened(db, pos.id, 1000.0, "AAPL", portfolio_id=p.id)
        db.commit()
        record_position_closed(db, pos.id, 1200.0, "AAPL", portfolio_id=p.id)
        db.commit()
        # -1000 + 1200 = +200 net
        assert p.cash == before + 200

    def test_reset_clears_transactions(self, db):
        p = ensure_portfolio(db, "bist")
        db.commit()
        pos = self._make_position(db, p.id)
        record_position_opened(db, pos.id, 500.0, "AAPL", portfolio_id=p.id)
        db.commit()
        reset_balance(db, p.id, starting_cash=25_000.0)
        db.commit()
        assert p.cash == 25_000.0
        assert db.query(BalanceTransaction).filter(
            BalanceTransaction.portfolio_id == p.id
        ).count() == 0
