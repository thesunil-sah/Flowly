"""SQLAlchemy declarative base — the single metadata Alembic autogenerates from."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
