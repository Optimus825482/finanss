import app.routers.balance as balance_router
from app.schemas.balance import BalanceDepositIn
from app.schemas.portfolio import PortfolioCloseIn, PortfolioPositionIn
from app.services.admin_service import _validate_public_url
from app.services.fair_value import dcf_fair_value


def test_balance_transactions_passes_limit_by_keyword(monkeypatch):
    calls = {}

    def fake_history(db, **kwargs):
        calls.update(kwargs)
        return []

    monkeypatch.setattr(balance_router, "get_transaction_history", fake_history)
    assert balance_router.api_get_transactions(limit=20, db=object()) == []
    assert calls == {"limit": 20}


def test_financial_inputs_reject_non_positive_values():
    for model, field in ((BalanceDepositIn, {"amount": 0}),
                         (PortfolioPositionIn, {"ticker": "AAPL", "quantity": 0, "entry_price": 10}),
                         (PortfolioCloseIn, {"exit_price": 0})):
        try:
            model(**field)
        except Exception:
            pass
        else:
            raise AssertionError(f"{model.__name__} accepted invalid value")


def test_dcf_rejects_invalid_terminal_growth_relationship():
    result = dcf_fair_value(1.0, wacc=0.05, terminal_growth=0.05)
    assert result["value"] is None


def test_provider_url_rejects_private_and_invalid_dns_targets():
    assert not _validate_public_url("http://127.0.0.1:8000")
    assert not _validate_public_url("not-a-url")
