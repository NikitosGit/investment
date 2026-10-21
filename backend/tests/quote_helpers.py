"""Shared factories and doubles for the quote service tests."""

from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import AssetType
from app.db.models.asset import Asset
from app.providers.moex.schemas import HistoryPoint

BASE_URL = "https://iss.moex.com/iss"
EMPTY_HISTORY = {"history": {"columns": ["TRADEDATE", "CLOSE"], "data": []}}


def create_stock(session: Session, secid: str = "SBER") -> Asset:
    asset = Asset(
        secid=secid,
        name=secid,
        type=AssetType.STOCK,
        engine="stock",
        market="shares",
        board="TQBR",
        currency="RUB",
        lot_size=1,
    )
    session.add(asset)
    session.commit()
    return asset


def create_bond(session: Session, secid: str = "SU26238RMFS4") -> Asset:
    asset = Asset(
        secid=secid,
        name=secid,
        type=AssetType.BOND,
        engine="stock",
        market="bonds",
        board="TQCB",
        currency="RUB",
        lot_size=1,
        initial_face_value_kopecks=100_000,
    )
    session.add(asset)
    session.commit()
    return asset


class HistoryClient:
    """Minimal provider double that returns predefined history points."""

    def __init__(self, points: list[HistoryPoint]) -> None:
        self.points = points
        self.calls: list[dict[str, Any]] = []

    def get_history(self, *args: Any, **kwargs: Any) -> list[HistoryPoint]:
        self.calls.append({"args": args, "kwargs": kwargs})
        return self.points
