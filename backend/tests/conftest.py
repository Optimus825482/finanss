"""Shared pytest fixtures for ORBIS FINAI backend tests.

Critical: DATABASE_URL must be set BEFORE importing app.config, because
app.config raises ValueError when the variable is missing. Importing any
app.* module (e.g. app.database) triggers app.config import.

Memory/LLM models use pgvector's Vector type which does not work on
SQLite, so conftest only registers core + balance + portfolio models.

SQLite in-memory (sqlite://) — her test koşusunda taze şema; kalıcı
test_orbis.db dosyasındaki eski index çakışmaları oluşmaz.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base

# Register ONLY SQLite-compatible models (core, balance, portfolio).
# Do NOT import app.models.memory / app.models.llm — they use pgvector Vector.
from app.models.core import *  # noqa: F401,F403
from app.models.balance import VirtualBalance, BalanceTransaction  # noqa: F401
from app.models.portfolio import Portfolio  # noqa: F401

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db():
    """Fresh session bound to a clean in-memory SQLite test DB per test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
