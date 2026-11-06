"""Asset lifecycle: MOEX search, creation, refresh and deletion.

Supported boards are ``TQBR`` (stocks), ``TQCB`` (corporate bonds) and
``TQOB`` (government bonds). An asset is uniquely identified by
``(secid, board)`` and tickers are normalized at the service boundary. MOEX
can move a security between boards (for example OFZ from ``TQCB`` to
``TQOB``), so refreshing an existing asset also resolves its current board.
"""

import json
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, IncomeStatus
from app.core.errors import AppError, ErrorCode
from app.core.time import today_local
from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.db.models.operation import Operation
from app.db.models.quote import Quote
from app.providers.moex import mapper
from app.providers.moex.client import MoexClient
from app.providers.moex.errors import MoexNotFound
from app.providers.moex.schemas import SecurityInfo, SecuritySearchResult
from app.services import bondization_service, portfolio_service


@dataclass(frozen=True, slots=True)
class AssetCard:
    """Everything the API needs to render an asset card."""

    asset: Asset
    current_face_value_kopecks: int | None
    amortizations: list[BondAmortization]


def normalize_secid(secid: str) -> str:
    """Normalize a ticker to the form stored by the application."""

    return secid.strip().upper()


def list_assets(session: Session, *, asset_type: AssetType | None = None) -> list[Asset]:
    """Return local assets ordered by id, optionally filtered by type."""

    statement = select(Asset).order_by(Asset.id)
    if asset_type is not None:
        statement = statement.where(Asset.type == asset_type)
    return list(session.scalars(statement))


def get_asset(session: Session, asset_id: int) -> Asset:
    """Return an asset or raise a 404 domain error."""

    asset = session.get(Asset, asset_id)
    if asset is None:
        raise AppError(
            ErrorCode.ASSET_NOT_FOUND,
            f"Актив {asset_id} не найден",
            status_code=404,
            details={"asset_id": asset_id},
        )
    return asset


def get_asset_card(session: Session, asset_id: int) -> AssetCard:
    """Return an asset together with its face value and amortization schedule."""

    return build_asset_card(session, get_asset(session, asset_id))


def build_asset_card(session: Session, asset: Asset) -> AssetCard:
    """Build the card view for an already loaded asset."""

    return AssetCard(
        asset=asset,
        current_face_value_kopecks=bondization_service.current_face_value_kopecks(
            session, asset, today_local()
        ),
        amortizations=bondization_service.list_amortizations(session, asset.id),
    )


def search_moex(client: MoexClient, query: str) -> list[SecuritySearchResult]:
    """Search MOEX for stocks and bonds on supported boards."""

    return client.search_securities(query.strip())


def create_from_moex(session: Session, client: MoexClient, *, secid: str, board: str) -> Asset:
    """Create a local asset from MOEX metadata in a single transaction."""

    market, asset_type = _board_spec(board)
    normalized_secid = normalize_secid(secid)
    if _find_asset(session, normalized_secid, board) is not None:
        raise AppError(
            ErrorCode.ASSET_ALREADY_EXISTS,
            f"Бумага {normalized_secid} на площадке {board} уже добавлена",
            status_code=409,
            details={"secid": normalized_secid, "board": board},
        )

    info = client.get_security_info(normalized_secid, board=board)
    _validate_info(info, asset_type)

    asset = Asset(
        secid=normalized_secid,
        isin=info.isin,
        name=info.name,
        short_name=info.short_name,
        type=asset_type,
        engine="stock",
        market=market,
        board=board,
        currency="RUB",
        lot_size=info.lot_size,
        initial_face_value_kopecks=(
            info.face_value_kopecks if asset_type is AssetType.BOND else None
        ),
        metadata_json=_dump_metadata(info),
    )
    session.add(asset)
    try:
        session.flush()
        _sync_bond_schedule(session, client, asset, asset_type)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(asset)
    return asset


def resolve_security_info(session: Session, client: MoexClient, asset: Asset) -> SecurityInfo:
    """Return MOEX metadata, following a security to its current board.

    The stored board is requested first. When MOEX no longer lists the
    security there (``MoexNotFound``), the primary/supported board is used
    instead. A switch is only accepted when the new board is supported and
    belongs to the same asset type; otherwise the original error is replaced
    with a domain error and the asset stays unchanged.

    The caller owns the transaction: this helper updates ``asset.board`` and
    ``asset.market`` in memory but never commits.
    """

    asset_type = asset.type
    _board_spec(asset.board)
    secid = normalize_secid(asset.secid)
    try:
        info = client.get_security_info(secid, board=asset.board)
    except MoexNotFound:
        info = client.get_security_info(secid)
        market, board_type = _board_spec(info.board)
        if board_type is not asset_type:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"Тип бумаги {info.secid} не соответствует площадке {info.board}",
                status_code=400,
                details={"secid": info.secid, "board": info.board, "type": info.type.value},
            ) from None
        _validate_info(info, asset_type)
        conflict = _find_asset(session, secid, info.board)
        if conflict is not None and conflict.id != asset.id:
            raise AppError(
                ErrorCode.ASSET_ALREADY_EXISTS,
                f"Бумага {secid} на площадке {info.board} уже добавлена",
                status_code=409,
                details={
                    "asset_id": asset.id,
                    "board": info.board,
                    "existing_asset_id": conflict.id,
                },
            ) from None
        asset.board = info.board
        asset.market = market
    else:
        _validate_info(info, asset_type)
    return info


def refresh_asset(session: Session, client: MoexClient, asset: Asset) -> Asset:
    """Refresh metadata (and bond schedules) of an existing asset atomically."""

    asset_type = asset.type
    try:
        info = resolve_security_info(session, client, asset)
        asset.secid = normalize_secid(asset.secid)
        asset.name = info.name
        asset.short_name = info.short_name
        asset.isin = info.isin
        asset.lot_size = info.lot_size
        asset.metadata_json = _dump_metadata(info)
        if asset_type is AssetType.BOND and info.face_value_kopecks is not None:
            asset.initial_face_value_kopecks = info.face_value_kopecks
        _sync_bond_schedule(session, client, asset, asset_type)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(asset)
    return asset


def delete_asset(session: Session, asset_id: int) -> None:
    """Delete an unused asset with its quotes, schedules and expected incomes.

    Paid incomes and operations are real history, so an asset that has them is
    kept. Expected coupons created by MOEX synchronization are derived data and
    are removed together with the asset.
    """

    asset = get_asset(session, asset_id)
    if _has_references(session, asset.id):
        raise AppError(
            ErrorCode.ASSET_IN_USE,
            "Нельзя удалить актив, по которому есть операции или выплаченные доходы",
            status_code=409,
            details={"asset_id": asset.id},
        )

    session.execute(delete(Income).where(Income.asset_id == asset.id))
    session.execute(delete(Quote).where(Quote.asset_id == asset.id))
    session.execute(delete(BondAmortization).where(BondAmortization.asset_id == asset.id))
    session.delete(asset)
    session.commit()


def _sync_bond_schedule(
    session: Session, client: MoexClient, asset: Asset, asset_type: AssetType
) -> None:
    if asset_type is not AssetType.BOND:
        return
    portfolio_id = portfolio_service.ensure_default_portfolio(session, commit=False).id
    bondization = client.get_bondization(asset.secid)
    bondization_service.sync_bondization(session, asset, bondization, portfolio_id=portfolio_id)


def _find_asset(session: Session, secid: str, board: str) -> Asset | None:
    return session.scalar(select(Asset).where(Asset.secid == secid, Asset.board == board))


def _board_spec(board: str) -> tuple[str, AssetType]:
    spec = mapper.BOARD_SPECS.get(board)
    if spec is None:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"Площадка {board} не поддерживается",
            status_code=400,
            details={"board": board, "supported": sorted(mapper.BOARD_SPECS)},
        )
    return spec


def _validate_info(info: SecurityInfo, asset_type: AssetType) -> None:
    """Validate that MOEX metadata matches the requested board.

    The provider derives ``SecurityInfo.type`` from the board, so the raw
    ``TYPE`` field is the only independent signal of a board/type mismatch.
    """

    raw_type = str(mapper.get_field(info.raw, "TYPE", "type") or "").strip().lower()
    if raw_type and ("bond" in raw_type) != (asset_type is AssetType.BOND):
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"Тип бумаги {info.secid} не соответствует площадке {info.board}",
            status_code=400,
            details={"secid": info.secid, "board": info.board, "raw_type": raw_type},
        )

    if asset_type is AssetType.BOND and info.face_value_kopecks is None:
        raise AppError(
            ErrorCode.MOEX_PARSE_ERROR,
            f"MOEX не вернул номинал облигации {info.secid}",
            status_code=502,
            details={"secid": info.secid},
        )


def _has_references(session: Session, asset_id: int) -> bool:
    operation_id = session.scalar(
        select(Operation.id).where(Operation.asset_id == asset_id).limit(1)
    )
    if operation_id is not None:
        return True
    paid_income_id = session.scalar(
        select(Income.id)
        .where(Income.asset_id == asset_id, Income.status == IncomeStatus.PAID)
        .limit(1)
    )
    return paid_income_id is not None


def _dump_metadata(info: SecurityInfo) -> str:
    return json.dumps(info.raw, ensure_ascii=False)
