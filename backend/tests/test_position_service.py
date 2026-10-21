"""Tests for operation replay and position valuation."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.enums import AssetType, DataSource, OperationType, PriceType
from app.core.errors import AppError, ErrorCode
from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.operation import Operation
from app.db.models.portfolio import Portfolio
from app.db.models.quote import Quote
from app.services import operation_service, portfolio_service, position_service


def _portfolio(session: Session) -> Portfolio:
    portfolio = portfolio_service.ensure_default_portfolio(session)
    assert portfolio.id == 1
    return portfolio


def _add_asset(
    session: Session,
    *,
    secid: str = "SBER",
    asset_type: AssetType = AssetType.STOCK,
    face_value_kopecks: int | None = None,
) -> Asset:
    asset = Asset(
        secid=secid,
        name=secid,
        type=asset_type,
        engine="stock",
        market="shares" if asset_type is AssetType.STOCK else "bonds",
        board="TQBR" if asset_type is AssetType.STOCK else "TQCB",
        currency="RUB",
        lot_size=1,
        initial_face_value_kopecks=face_value_kopecks,
    )
    session.add(asset)
    session.commit()
    return asset


def _add_quote(
    session: Session,
    asset: Asset,
    *,
    price_micro: int,
    quote_date: date | None = None,
    price_type: PriceType = PriceType.RUB,
    source: DataSource = DataSource.MOEX,
) -> Quote:
    quote = Quote(
        asset_id=asset.id,
        quote_date=quote_date or today_local(),
        price_micro=price_micro,
        price_type=price_type,
        source=source,
    )
    session.add(quote)
    session.commit()
    return quote


def _create_op(
    session: Session,
    asset: Asset,
    *,
    operation_type: OperationType = OperationType.BUY,
    trade_date: date = date(2026, 1, 10),
    quantity: int = 10,
    price: Decimal = Decimal("100"),
    price_type: PriceType = PriceType.RUB,
) -> Operation:
    return operation_service.create_operation(
        session,
        asset_id=asset.id,
        type=operation_type,
        trade_date=trade_date,
        quantity=quantity,
        price=price,
        price_type=price_type,
        note=None,
    )


def _buy(
    session: Session, asset: Asset, *, quantity: int, price: Decimal, trade_date: date
) -> Operation:
    return _create_op(session, asset, trade_date=trade_date, quantity=quantity, price=price)


def test_backdated_buy_recalculates_later_sell(db_session: Session) -> None:
    asset = _add_asset(db_session)
    _create_op(db_session, asset, quantity=10)
    _create_op(
        db_session,
        asset,
        operation_type=OperationType.SELL,
        trade_date=date(2026, 1, 20),
        price=Decimal("150"),
    )
    assert position_service.validate_operation_sequence(db_session, asset.id).quantity == 0

    _buy(db_session, asset, quantity=5, price=Decimal("200"), trade_date=date(2026, 1, 15))

    state = position_service.validate_operation_sequence(db_session, asset.id)
    assert [
        operation.trade_date for operation in position_service.load_operations(db_session, asset.id)
    ] == [
        date(2026, 1, 10),
        date(2026, 1, 15),
        date(2026, 1, 20),
    ]
    assert state.quantity == 5
    assert state.cost_kopecks == 66_667
    assert state.avg_price_micro == 133_334_000


def test_bond_percent_price_is_normalized(db_session: Session) -> None:
    asset = _add_asset(
        db_session,
        secid="SU26238RMFS4",
        asset_type=AssetType.BOND,
        face_value_kopecks=100_000,
    )

    operation = _create_op(
        db_session,
        asset,
        trade_date=date(2026, 2, 1),
        quantity=15,
        price=Decimal("95.123"),
        price_type=PriceType.PERCENT,
    )

    assert operation.price_micro == 951_230_000
    assert operation.input_price_micro == 95_123_000
    assert operation.input_price_type is PriceType.PERCENT
    assert operation.face_value_kopecks == 100_000
    state = position_service.validate_operation_sequence(db_session, asset.id)
    assert state.avg_price_micro == 951_230_000


def test_create_operation_rejects_non_positive_values(db_session: Session) -> None:
    asset = _add_asset(db_session)

    with pytest.raises(AppError) as quantity_error:
        _create_op(db_session, asset, quantity=0)
    assert quantity_error.value.code == ErrorCode.BAD_REQUEST

    with pytest.raises(AppError) as price_error:
        _create_op(db_session, asset, quantity=1, price=Decimal("0.0000001"))
    assert price_error.value.code == ErrorCode.BAD_REQUEST


def test_without_quote_position_falls_back_to_cost(db_session: Session) -> None:
    asset = _add_asset(db_session)
    _buy(db_session, asset, quantity=10, price=Decimal("100"), trade_date=date(2026, 1, 10))

    view = position_service.get_position(db_session, asset.id)

    assert view.current_price_micro == 100_000_000
    assert view.current_price_type is PriceType.RUB
    assert view.current_face_value_kopecks is None
    assert view.market_value_kopecks == view.invested_kopecks == 100_000
    assert view.price_date is None
    assert view.price_source == "COST"
    assert view.is_stale is True
    assert view.share == Decimal("1.0000")


def test_quote_valuations_for_stock_and_bond(db_session: Session) -> None:
    stock = _add_asset(db_session, secid="SBER")
    _buy(db_session, stock, quantity=10, price=Decimal("100"), trade_date=date(2026, 1, 10))
    _buy(db_session, stock, quantity=10, price=Decimal("120"), trade_date=date(2026, 1, 11))
    _add_quote(db_session, stock, price_micro=310_500_000)

    bond = _add_asset(
        db_session,
        secid="SU26238RMFS4",
        asset_type=AssetType.BOND,
        face_value_kopecks=100_000,
    )
    operation_service.create_operation(
        db_session,
        asset_id=bond.id,
        type=OperationType.BUY,
        trade_date=date(2026, 2, 1),
        quantity=15,
        price=Decimal("95.123"),
        price_type=PriceType.PERCENT,
        note=None,
    )
    _add_quote(db_session, bond, price_micro=98_500_000, price_type=PriceType.PERCENT)

    stock_view = position_service.get_position(db_session, stock.id)
    assert stock_view.current_price_micro == 310_500_000
    assert stock_view.current_price_type is PriceType.RUB
    assert stock_view.market_value_kopecks == 621_000
    assert stock_view.price_date == today_local()
    assert stock_view.price_source == "MOEX"
    assert stock_view.is_stale is False

    bond_view = position_service.get_position(db_session, bond.id)
    assert bond_view.current_price_type is PriceType.PERCENT
    assert bond_view.current_price_micro == 98_500_000
    assert bond_view.current_face_value_kopecks == 100_000
    assert bond_view.market_value_kopecks == 1_477_500
    assert bond_view.invested_kopecks == 1_426_845


def test_bond_market_value_uses_face_on_quote_date(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(position_service, "today_local", lambda: date(2026, 3, 10))
    bond = _add_asset(
        db_session,
        secid="SU26238RMFS4",
        asset_type=AssetType.BOND,
        face_value_kopecks=100_000,
    )
    _create_op(
        db_session,
        bond,
        trade_date=date(2026, 2, 1),
        quantity=2,
        price=Decimal("95"),
        price_type=PriceType.PERCENT,
    )
    db_session.add(
        BondAmortization(
            asset_id=bond.id,
            amortization_date=date(2026, 3, 1),
            amount_per_unit_kopecks=20_000,
            source=DataSource.MOEX,
        )
    )
    db_session.commit()

    _add_quote(
        db_session,
        bond,
        price_micro=95_000_000,
        quote_date=date(2026, 2, 15),
        price_type=PriceType.PERCENT,
    )
    before_amortization = position_service.get_position(db_session, bond.id)
    assert before_amortization.market_value_kopecks == 190_000
    assert before_amortization.current_face_value_kopecks == 80_000

    _add_quote(
        db_session,
        bond,
        price_micro=95_000_000,
        quote_date=date(2026, 3, 5),
        price_type=PriceType.PERCENT,
    )
    after_amortization = position_service.get_position(db_session, bond.id)
    assert after_amortization.market_value_kopecks == 152_000
    assert after_amortization.price_date == date(2026, 3, 5)


def test_bond_ruble_quote_uses_price_per_unit(db_session: Session) -> None:
    bond = _add_asset(
        db_session,
        secid="SU26238RMFS4",
        asset_type=AssetType.BOND,
        face_value_kopecks=100_000,
    )
    _create_op(
        db_session,
        bond,
        trade_date=date(2026, 2, 1),
        quantity=2,
        price=Decimal("95"),
        price_type=PriceType.PERCENT,
    )
    _add_quote(
        db_session,
        bond,
        price_micro=900_000_000,
        price_type=PriceType.RUB,
        source=DataSource.MANUAL,
    )

    view = position_service.get_position(db_session, bond.id)

    assert view.current_price_type is PriceType.RUB
    assert view.current_price_micro == 900_000_000
    assert view.market_value_kopecks == 180_000
    assert view.invested_kopecks == 190_000
    assert view.current_face_value_kopecks == 100_000
    assert view.price_source == "MANUAL"


def test_shares_sum_to_one(db_session: Session) -> None:
    sber = _add_asset(db_session, secid="SBER")
    _buy(db_session, sber, quantity=10, price=Decimal("100"), trade_date=date(2026, 1, 10))
    _buy(db_session, sber, quantity=10, price=Decimal("120"), trade_date=date(2026, 1, 11))
    _add_quote(db_session, sber, price_micro=310_500_000)

    gazp = _add_asset(db_session, secid="GAZP")
    _buy(db_session, gazp, quantity=10, price=Decimal("200"), trade_date=date(2026, 1, 10))
    _add_quote(db_session, gazp, price_micro=150_000_000)

    views = position_service.get_positions(db_session)

    assert [view.asset.secid for view in views] == ["SBER", "GAZP"]
    assert [view.share for view in views] == [Decimal("0.8054"), Decimal("0.1946")]
    assert sum(view.share for view in views) == Decimal("1.0000")
    assert position_service.get_position(db_session, sber.id).share == Decimal("0.8054")


def test_closed_position_is_excluded_and_readable(db_session: Session) -> None:
    closed = _add_asset(db_session, secid="SBER")
    _buy(db_session, closed, quantity=10, price=Decimal("100"), trade_date=date(2026, 1, 10))
    operation_service.create_operation(
        db_session,
        asset_id=closed.id,
        type=OperationType.SELL,
        trade_date=date(2026, 1, 20),
        quantity=10,
        price=Decimal("150"),
        price_type=PriceType.RUB,
        note=None,
    )
    open_asset = _add_asset(db_session, secid="GAZP")
    _buy(db_session, open_asset, quantity=5, price=Decimal("200"), trade_date=date(2026, 1, 10))

    views = position_service.get_positions(db_session)
    assert [view.asset.secid for view in views] == ["GAZP"]

    closed_view = position_service.get_position(db_session, closed.id)
    assert closed_view.state.quantity == 0
    assert closed_view.market_value_kopecks == 0
    assert closed_view.share == Decimal("0.0000")


def test_stale_quote_is_flagged(db_session: Session) -> None:
    asset = _add_asset(db_session)
    _buy(db_session, asset, quantity=1, price=Decimal("100"), trade_date=date(2026, 1, 10))
    _add_quote(
        db_session, asset, price_micro=120_000_000, quote_date=today_local() - timedelta(days=3)
    )

    view = position_service.get_position(db_session, asset.id)

    assert view.is_stale is True
    assert view.price_source == "MOEX"
    assert view.market_value_kopecks == 12_000


def test_invalid_stored_history_is_rejected(db_session: Session) -> None:
    asset = _add_asset(db_session)
    portfolio = _portfolio(db_session)
    db_session.add(
        Operation(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            type=OperationType.SELL,
            trade_date=date(2026, 1, 10),
            quantity=1,
            price_micro=100_000_000,
            input_price_micro=100_000_000,
            input_price_type=PriceType.RUB,
        )
    )
    db_session.commit()

    with pytest.raises(AppError) as exc_info:
        position_service.validate_operation_sequence(db_session, asset.id)

    assert exc_info.value.code == ErrorCode.INSUFFICIENT_QUANTITY
