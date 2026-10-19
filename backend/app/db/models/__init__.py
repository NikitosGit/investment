"""ORM models. Importing this package registers every table in ``Base.metadata``."""

from app.db.models.asset import Asset
from app.db.models.bond import BondAmortization
from app.db.models.income import Income
from app.db.models.operation import Operation
from app.db.models.portfolio import DEFAULT_PORTFOLIO_NAME, Portfolio
from app.db.models.quote import Quote
from app.db.models.setting import AppSetting
from app.db.models.snapshot import PortfolioSnapshot

__all__ = [
    "DEFAULT_PORTFOLIO_NAME",
    "AppSetting",
    "Asset",
    "BondAmortization",
    "Income",
    "Operation",
    "Portfolio",
    "PortfolioSnapshot",
    "Quote",
]
