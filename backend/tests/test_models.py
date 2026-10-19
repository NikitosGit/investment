"""ORM model constraint and type tests."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import (
    AssetType,
    DataSource,
    IncomeKind,
    IncomeStatus,
    OperationType,
    PriceType,
)
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.db.models.operation import Operation
from app.db.models.portfolio import Portfolio
from app.db.models.quote import Quote


def _portfolio(session: Session) -> Portfolio:
    portfolio = Portfolio(name="Тест", base_currency="RUB")
    session.add(portfolio)
    session.commit()
    return portfolio


def _asset(session: Session, portfolio: Portfolio, secid: str = "SBER") -> Asset:
    asset = Asset(
        secid=secid,
        name="Сбербанк",
        type=AssetType.STOCK,
        engine="stock",
        market="shares",
        board="TQBR",
        currency="RUB",
    )
    session.add(asset)
    session.commit()
    return asset


def test_asset_enums_round_trip(db_session: Session) -> None:
    asset = _asset(db_session, _portfolio(db_session))
    db_session.expire_all()

    reloaded = db_session.get(Asset, asset.id)
    assert reloaded is not None
    assert reloaded.type is AssetType.STOCK


def test_asset_secid_and_board_must_be_unique(db_session: Session) -> None:
    portfolio = _portfolio(db_session)
    _asset(db_session, portfolio)

    with pytest.raises(IntegrityError):
        _asset(db_session, portfolio)
    db_session.rollback()


def test_operation_quantity_must_be_positive(db_session: Session) -> None:
    portfolio = _portfolio(db_session)
    asset = _asset(db_session, portfolio)

    db_session.add(
        Operation(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            type=OperationType.BUY,
            trade_date=date(2026, 1, 10),
            quantity=0,
            price_micro=100_000_000,
            input_price_micro=100_000_000,
            input_price_type=PriceType.RUB,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_operation_price_must_be_positive(db_session: Session) -> None:
    portfolio = _portfolio(db_session)
    asset = _asset(db_session, portfolio)

    db_session.add(
        Operation(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            type=OperationType.BUY,
            trade_date=date(2026, 1, 10),
            quantity=1,
            price_micro=0,
            input_price_micro=0,
            input_price_type=PriceType.RUB,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_quote_price_must_be_positive(db_session: Session) -> None:
    portfolio = _portfolio(db_session)
    asset = _asset(db_session, portfolio)

    db_session.add(
        Quote(
            asset_id=asset.id,
            quote_date=date(2026, 1, 10),
            price_micro=0,
            price_type=PriceType.RUB,
            source=DataSource.MOEX,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_amortization_amount_must_be_positive(db_session: Session) -> None:
    portfolio = _portfolio(db_session)
    asset = _asset(db_session, portfolio)

    db_session.add(
        BondAmortization(
            asset_id=asset.id,
            amortization_date=date(2026, 1, 10),
            amount_per_unit_kopecks=0,
            source=DataSource.MOEX,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def _income(portfolio_id: int, asset_id: int, external_id: str | None) -> Income:
    return Income(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        kind=IncomeKind.COUPON,
        status=IncomeStatus.PAID,
        amount_total_kopecks=3_500,
        currency="RUB",
        pay_date=date(2026, 6, 1),
        source=DataSource.MANUAL,
        external_id=external_id,
    )


def test_income_external_id_allows_multiple_nulls(db_session: Session) -> None:
    portfolio = _portfolio(db_session)
    asset = _asset(db_session, portfolio)

    db_session.add_all(
        [_income(portfolio.id, asset.id, None), _income(portfolio.id, asset.id, None)]
    )
    db_session.commit()

    assert db_session.query(Income).count() == 2


def test_income_external_id_must_be_unique(db_session: Session) -> None:
    portfolio = _portfolio(db_session)
    asset = _asset(db_session, portfolio)

    db_session.add_all(
        [
            _income(portfolio.id, asset.id, "moex:coupon:SBER:2026-06-01"),
            _income(portfolio.id, asset.id, "moex:coupon:SBER:2026-06-01"),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_only_single_portfolio_row_allowed(db_session: Session) -> None:
    _portfolio(db_session)

    db_session.add(Portfolio(name="Второй портфель", base_currency="RUB"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
