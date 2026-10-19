"""Portfolio API schemas."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.schemas.common import ApiModel, UtcDatetime

PortfolioName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class PortfolioResponse(ApiModel):
    """The single portfolio."""

    id: int
    name: str
    base_currency: str
    created_at: UtcDatetime


class PortfolioUpdate(BaseModel):
    """Editable portfolio fields."""

    name: PortfolioName
