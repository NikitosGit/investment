"""Declarative base and shared SQLAlchemy metadata conventions."""

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def db_enum(enum_cls: type[StrEnum], *, length: int = 10) -> SAEnum:
    """Store a Python enum as a validated VARCHAR column.

    SQLite has no native enum type, so values are persisted as strings.
    """

    def _values(enum_type: type[StrEnum]) -> list[str]:
        return [member.value for member in enum_type]

    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=_values,
        validate_strings=True,
        create_constraint=False,
    )
