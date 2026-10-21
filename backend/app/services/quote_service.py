"""Quote lookups.

This stage only needs the read side used by position valuation. Fetching from
MOEX, history backfilling and manual quotes arrive in stage 6, which extends
this module without changing :func:`get_last_quote`.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import today_local
from app.db.models.quote import Quote


def get_last_quote(session: Session, asset_id: int, on_date: date | None = None) -> Quote | None:
    """Return the latest quote with ``quote_date <= on_date``.

    ``on_date`` defaults to today in the configured timezone. Ties on the same
    date resolve to the newest row id, so re-imported or corrected quotes win.
    """

    target = on_date if on_date is not None else today_local()
    statement = (
        select(Quote)
        .where(Quote.asset_id == asset_id, Quote.quote_date <= target)
        .order_by(Quote.quote_date.desc(), Quote.id.desc())
        .limit(1)
    )
    return session.scalars(statement).first()
