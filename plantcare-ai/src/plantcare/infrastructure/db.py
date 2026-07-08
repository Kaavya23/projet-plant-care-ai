"""Fabrique d'engine / session SQLAlchemy pour la base de service."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from plantcare.config import settings
from plantcare.infrastructure.models_orm import Base


def get_engine(url: str | None = None):
    return create_engine(url or settings.database_url, future=True)


def init_db(url: str | None = None) -> None:
    """Crée les tables (idempotent)."""
    Base.metadata.create_all(get_engine(url))


def get_session(url: str | None = None):
    return sessionmaker(bind=get_engine(url), expire_on_commit=False, future=True)()
