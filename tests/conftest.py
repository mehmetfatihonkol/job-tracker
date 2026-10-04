import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import database
from app.config import Settings
from app.main import create_app
from app.repository import ApplicationRepository

FIXED_NOW = datetime(2026, 10, 4, 12, 0, 0)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, database_path=tmp_path / "test.db", openai_api_key=None)


@pytest.fixture
def conn(settings: Settings) -> Iterator[sqlite3.Connection]:
    with database.transaction(settings.database_path) as connection:
        database.migrate(connection)
        yield connection


@pytest.fixture
def repo(conn: sqlite3.Connection) -> ApplicationRepository:
    return ApplicationRepository(conn, now=lambda: FIXED_NOW)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
