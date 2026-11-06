"""Board resolution for assets whose MOEX board has changed."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy.orm import Session

from app.core.enums import AssetType
from app.core.errors import AppError
from app.db.models.asset import Asset
from app.providers.moex.client import MoexClient
from app.services import asset_service

from asset_helpers import BASE_URL, security_payload  # isort: skip
from quote_helpers import create_bond  # isort: skip


@respx.mock
def test_resolve_security_info_moves_legacy_tqcb_bond_to_tqob(
    db_session: Session,
    moex_client: MoexClient,
    load_fixture: Callable[..., Any],
) -> None:
    asset = create_bond(db_session)
    board_payload = load_fixture("moex", "security_su26238_tqob_board.json")
    lot_size_index = board_payload["securities"]["columns"].index("LOTSIZE")
    board_payload["securities"]["data"][0][lot_size_index] = 5
    respx.get(f"{BASE_URL}/securities/SU26238RMFS4.json").mock(
        side_effect=[
            # Requested TQCB is absent, so the first call raises MoexNotFound.
            httpx.Response(200, json=load_fixture("moex", "security_su26238_tqob.json")),
            # The board-less retry resolves the primary TQOB board.
            httpx.Response(200, json=load_fixture("moex", "security_su26238_tqob.json")),
        ]
    )
    respx.get(
        f"{BASE_URL}/engines/stock/markets/bonds/boards/TQOB/securities/SU26238RMFS4.json"
    ).mock(return_value=httpx.Response(200, json=board_payload))

    info = asset_service.resolve_security_info(db_session, moex_client, asset)

    assert info.board == "TQOB"
    assert info.type is AssetType.BOND
    assert info.lot_size == 5
    assert asset.board == "TQOB"
    assert asset.market == "bonds"


@respx.mock
def test_resolve_security_info_rejects_existing_asset_on_new_board(
    db_session: Session,
    moex_client: MoexClient,
    load_fixture: Callable[..., Any],
) -> None:
    legacy = create_bond(db_session)
    existing = Asset(
        secid="SU26238RMFS4",
        name="ОФЗ 26238",
        type=AssetType.BOND,
        engine="stock",
        market="bonds",
        board="TQOB",
        currency="RUB",
        lot_size=1,
        initial_face_value_kopecks=100_000,
    )
    db_session.add(existing)
    db_session.commit()

    respx.get(f"{BASE_URL}/securities/SU26238RMFS4.json").mock(
        side_effect=[
            httpx.Response(200, json=load_fixture("moex", "security_su26238_tqob.json")),
            httpx.Response(200, json=load_fixture("moex", "security_su26238_tqob.json")),
        ]
    )
    respx.get(
        f"{BASE_URL}/engines/stock/markets/bonds/boards/TQOB/securities/SU26238RMFS4.json"
    ).mock(
        return_value=httpx.Response(
            200, json=load_fixture("moex", "security_su26238_tqob_board.json")
        )
    )

    with pytest.raises(AppError) as exc_info:
        asset_service.resolve_security_info(db_session, moex_client, legacy)

    assert exc_info.value.code == "ASSET_ALREADY_EXISTS"
    assert exc_info.value.status_code == 409
    assert exc_info.value.details == {
        "asset_id": legacy.id,
        "board": "TQOB",
        "existing_asset_id": existing.id,
    }
    assert legacy.board == "TQCB"
    assert legacy.market == "bonds"


@respx.mock
def test_resolve_security_info_rejects_board_type_mismatch(
    db_session: Session,
    moex_client: MoexClient,
    load_fixture: Callable[..., Any],
) -> None:
    asset = create_bond(db_session, "SBER")
    respx.get(f"{BASE_URL}/securities/SBER.json").mock(
        side_effect=[
            httpx.Response(200, json=load_fixture("moex", "security_sber.json")),
            httpx.Response(200, json=load_fixture("moex", "security_sber.json")),
        ]
    )

    with pytest.raises(AppError) as exc_info:
        asset_service.resolve_security_info(db_session, moex_client, asset)

    assert exc_info.value.code == "BAD_REQUEST"
    assert exc_info.value.status_code == 400
    assert exc_info.value.details["board"] == "TQBR"
    assert asset.board == "TQCB"
    assert asset.market == "bonds"


@respx.mock
def test_resolve_security_info_rejects_board_type_without_raw_type(
    db_session: Session,
    moex_client: MoexClient,
) -> None:
    """The board itself is a type signal when MOEX omits the raw TYPE field."""

    asset = create_bond(db_session, "NOTYPE")
    payload = security_payload(
        secid="NOTYPE",
        board="TQBR",
        security_type="",
        face_value=1000.0,
    )
    respx.get(f"{BASE_URL}/securities/NOTYPE.json").mock(
        side_effect=[
            httpx.Response(200, json=payload),
            httpx.Response(200, json=payload),
        ]
    )

    with pytest.raises(AppError) as exc_info:
        asset_service.resolve_security_info(db_session, moex_client, asset)

    assert exc_info.value.code == "BAD_REQUEST"
    assert exc_info.value.status_code == 400
    assert exc_info.value.details["board"] == "TQBR"
    assert asset.board == "TQCB"
    assert asset.market == "bonds"


@respx.mock
def test_resolve_security_info_rejects_unsupported_board(
    db_session: Session,
    moex_client: MoexClient,
) -> None:
    asset = create_bond(db_session, "BADBOARD")
    payload = security_payload(
        secid="BADBOARD",
        board="TQTF",
        security_type="ofz_bond",
        face_value=1000.0,
    )
    respx.get(f"{BASE_URL}/securities/BADBOARD.json").mock(
        side_effect=[
            httpx.Response(200, json=payload),
            httpx.Response(200, json=payload),
        ]
    )

    with pytest.raises(AppError) as exc_info:
        asset_service.resolve_security_info(db_session, moex_client, asset)

    assert exc_info.value.code == "BAD_REQUEST"
    assert exc_info.value.status_code == 400
    assert exc_info.value.details["board"] == "TQTF"
    assert asset.board == "TQCB"
