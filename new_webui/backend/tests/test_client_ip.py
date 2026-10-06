"""
Which address a request is attributed to: the audit trail's ``ip`` and the key
the sign-in throttle counts failures against.

Only the connection's peer address counts. Forwarding headers are honoured
by uvicorn's proxy-headers middleware, and only from a peer listed in
FORWARDED_ALLOW_IPS; the app itself never reads them. Otherwise any client
could write whatever address it liked into the audit trail and start each
password guess under a fresh address to dodge the throttle.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.requests import Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app import audit
from app.config import Settings
from app.db import connect
from app.main import create_app
from tests.conftest import add_user

PROXY = "172.30.57.10"  # the web container in deploy/docker-compose.yml
CLIENT = "192.168.10.77"
SPOOFED = {"X-Forwarded-For": "10.9.9.9", "X-Real-IP": "10.9.9.9"}


def _echo_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ip")
    def ip(request: Request) -> dict:
        return {"ip": audit.client_ip(request)}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"ip": audit.client_ip(websocket)})
        await websocket.close()

    return app


def test_forwarding_headers_are_ignored_without_a_trusted_proxy():
    client = TestClient(_echo_app(), client=(CLIENT, 40000))
    assert client.get("/ip", headers=SPOOFED).json() == {"ip": CLIENT}


def test_a_websocket_is_attributed_the_same_way():
    client = TestClient(_echo_app(), client=(CLIENT, 40000))
    with client.websocket_connect("/ws", headers=SPOOFED) as websocket:
        assert websocket.receive_json() == {"ip": CLIENT}


def test_the_trusted_proxy_supplies_the_client_address():
    # What uvicorn does with --proxy-headers and FORWARDED_ALLOW_IPS=<proxy>.
    app = ProxyHeadersMiddleware(_echo_app(), trusted_hosts=PROXY)
    client = TestClient(app, client=(PROXY, 40000))
    assert client.get("/ip", headers={"X-Forwarded-For": CLIENT}).json() == {"ip": CLIENT}


def test_forwarding_headers_from_anyone_else_are_ignored():
    app = ProxyHeadersMiddleware(_echo_app(), trusted_hosts=PROXY)
    client = TestClient(app, client=(CLIENT, 40000))
    assert client.get("/ip", headers=SPOOFED).json() == {"ip": CLIENT}


def test_x_real_ip_is_not_trusted_even_from_loopback():
    # The previous helper took X-Real-IP from 127.0.0.1, which in the Docker
    # deployment is not the only thing that can reach the backend.
    client = TestClient(_echo_app(), client=("127.0.0.1", 40000))
    assert client.get("/ip", headers={"X-Real-IP": "10.9.9.9"}).json() == {"ip": "127.0.0.1"}


# ── Through the real app ──────────────────────────────────────────────────────


@pytest.fixture
def app_settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        env="development",
        db_path=tmp_path / "test.db",
        maps_dir=tmp_path / "maps",
        cors_origins=["http://localhost:3100"],
    )


@pytest.fixture
def direct(app_settings: Settings) -> Iterator[TestClient]:
    """A client connecting straight to the backend, not through the proxy."""
    with TestClient(create_app(app_settings), client=(CLIENT, 40000)) as client:
        yield client


def _login(client: TestClient, username: str, password: str, **headers: str):
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}, headers=headers
    )


def test_the_audit_trail_records_the_peer_not_a_forged_header(direct, app_settings):
    add_user(app_settings, "viewer", "dina")
    _login(direct, "dina", "wrong-password", **SPOOFED)

    conn = connect(app_settings.db_path)
    try:
        ips = [row["ip"] for row in conn.execute("SELECT ip FROM audit_log")]
    finally:
        conn.close()
    assert ips == [CLIENT]


def test_a_forged_address_does_not_reset_the_sign_in_throttle(direct, app_settings):
    add_user(app_settings, "viewer", "guessme")
    for n in range(5):
        forged = f"10.0.0.{n}"
        response = _login(
            direct, "guessme", "wrong-password", **{"X-Forwarded-For": forged, "X-Real-IP": forged}
        )
        assert response.status_code == 401

    response = _login(direct, "guessme", "wrong-password", **{"X-Forwarded-For": "10.0.0.99"})
    assert response.status_code == 429


def test_behind_the_trusted_proxy_each_client_is_throttled_on_its_own(app_settings):
    app = ProxyHeadersMiddleware(create_app(app_settings), trusted_hosts=PROXY)
    with TestClient(app, client=(PROXY, 40000)) as proxy:
        add_user(app_settings, "viewer", "shared")  # after start-up has migrated the db
        desk = {"X-Forwarded-For": CLIENT}
        for _ in range(5):
            assert _login(proxy, "shared", "wrong-password", **desk).status_code == 401
        assert _login(proxy, "shared", "wrong-password", **desk).status_code == 429

        # Someone at another desk is not locked out by that.
        other = {"X-Forwarded-For": "192.168.10.78"}
        assert _login(proxy, "shared", "wrong-password", **other).status_code == 401
