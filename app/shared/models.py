"""Shared SQLAlchemy declarative base for all modules."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
