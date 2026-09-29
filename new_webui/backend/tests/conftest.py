from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect, migrate
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Each test gets its own database file, so nothing leaks between them."""
    return Settings(
        env="development",
        db_path=tmp_path / "test.db",
        maps_dir=tmp_path / "maps",
        cors_origins=["http://localhost:3100"],
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def connection(settings: Settings):
    conn = connect(settings.db_path)
    migrate(conn)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def robot_payload() -> dict:
    return {"name": "AMR-01", "bridge_url": "ws://192.168.1.50:8765"}
