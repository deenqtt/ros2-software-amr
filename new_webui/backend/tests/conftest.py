from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE
from app.config import Settings
from app.db import connect, migrate
from app.main import create_app
from app.repositories import users as users_repo
from app.security import hash_password, hash_token, new_session_token

PASSWORD = "correct-horse-battery"  # noqa: S105 — test fixture
# Hashed once: scrypt is slow on purpose, and most tests only need someone
# signed in, not a fresh hash each.
_PASSWORD_HASH = hash_password(PASSWORD)


def add_user(settings: Settings, role: str, username: str | None = None) -> dict:
    """An account with PASSWORD, written straight to the database."""
    conn = connect(settings.db_path)
    try:
        row = users_repo.create_user(
            conn,
            {
                "username": username or f"{role}-{uuid.uuid4().hex[:6]}",
                "role": role,
                "password_hash": _PASSWORD_HASH,
            },
        )
        return dict(row)
    finally:
        conn.close()


def open_session(settings: Settings, user_id: str) -> str:
    """A signed-in session for this user, without going through /login."""
    token = new_session_token()
    conn = connect(settings.db_path)
    try:
        users_repo.create_session(conn, hash_token(token), user_id, "pytest")
    finally:
        conn.close()
    return token


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """
    Each test gets its own database file, so nothing leaks between them.

    And never the developer's .env: a bootstrap account or an agent mode set
    there would quietly change what every test is testing.
    """
    return Settings(
        _env_file=None,
        env="development",
        db_path=tmp_path / "test.db",
        maps_dir=tmp_path / "maps",
        cors_origins=["http://localhost:3100"],
    )


@pytest.fixture
def anon_client(settings: Settings) -> Iterator[TestClient]:
    """Nobody signed in."""
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_as(anon_client: TestClient, settings: Settings) -> Callable[..., TestClient]:
    """``client_as("operator")``: a client signed in with that role, on the same app."""

    def make(role: str, username: str | None = None) -> TestClient:
        user = add_user(settings, role, username)
        test_client = TestClient(anon_client.app)
        test_client.cookies.set(SESSION_COOKIE, open_session(settings, user["id"]))
        test_client.user = user  # type: ignore[attr-defined]
        return test_client

    return make


@pytest.fixture
def client(client_as) -> TestClient:
    """Signed in as a super admin, who may do everything. Most tests are about behaviour."""
    return client_as("super_admin", "admin")


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
