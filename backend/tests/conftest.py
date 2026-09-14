"""Isolated test configuration for the VERA backend."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Must be set before importing any app module because Settings is instantiated
# at import time. The SQLite file also permits TestClient's worker thread.
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["MODEL_DIR"] = "data/models-test"
os.environ["ENVIRONMENT"] = "test"

from app.database import Base, SessionLocal, engine
from app.main import create_app


@pytest.fixture(autouse=True)
def database() -> Generator[None, None, None]:
    """Create a completely fresh relational schema for every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(create_app()) as test_client:
        yield test_client
