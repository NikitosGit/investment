"""Portfolio read/update operations.

The application supports exactly one portfolio, created on first access.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.portfolio import DEFAULT_PORTFOLIO_NAME, Portfolio


def get_portfolio(session: Session) -> Portfolio | None:
    """Return the single portfolio or ``None`` if it does not exist yet."""

    return session.scalars(select(Portfolio).order_by(Portfolio.id)).first()


def ensure_default_portfolio(session: Session, *, commit: bool = True) -> Portfolio:
    """Return the portfolio, creating the default one when absent.

    With ``commit=False`` the new row is only flushed, so it participates in
    the caller's transaction and is rolled back together with it.
    """

    portfolio = get_portfolio(session)
    if portfolio is not None:
        return portfolio

    portfolio = Portfolio(name=DEFAULT_PORTFOLIO_NAME, base_currency="RUB")
    session.add(portfolio)
    if commit:
        session.commit()
        session.refresh(portfolio)
    else:
        session.flush()
    return portfolio


def rename_portfolio(session: Session, name: str) -> Portfolio:
    """Rename the single portfolio."""

    portfolio = ensure_default_portfolio(session)
    portfolio.name = name
    session.commit()
    session.refresh(portfolio)
    return portfolio
