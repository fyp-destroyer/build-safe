"""Shared declarative base for all SQLAlchemy models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base — every ORM model in this package inherits from this."""
