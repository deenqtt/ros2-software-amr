"""
Session lifetime, the password policy, and the throttles that protect both.

A session ends after a fixed time however busy it is; every password that is
set meets one policy, wherever it is set; guessing the current password on the
change-password form is throttled like sign-in; and the throttle's memory is
bounded, however many names a guesser tries.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import __main__ as cli
from app.api import auth as auth_api
from app.api.auth import FAILURE_WINDOW_S, FAILURES_ALLOWED, LoginThrottle
from app.auth import SESSION_COOKIE
from app.config import Settings
from app.db import connect
from app.repositories import users as users_repo
from app.security import PASSWORD_MAX, PASSWORD_MIN, hash_password, password_problem
from tests.conftest import PASSWORD
from tests.test_ros_proxy import ORIGIN, FakeRobot


def login(client: TestClient, username: str, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def _age_sessions(settings: Settings, hours: float) -> None:
    """Sessions signed in ``hours`` ago, but used just now."""
    conn = connect(settings.db_path)
    try:
        conn.execute(
            "UPDATE sessions SET created_at = datetime('now', ?), last_seen_at = datetime('now')",
            (f"-{int(hours * 60)} minutes",),
        )
    finally:
        conn.close()


# ── Absolute session lifetime ────────────────────────────────────────────────


def test_default_lifetime_covers_a_shift_and_no_more():
    settings = Settings(_env_file=None)
    assert settings.session_max_hours == 14
    assert settings.session_max_hours * 60 >= settings.session_idle_minutes


def test_a_busy_session_still_ends_at_its_maximum_age(client_as, settings):
    viewer = client_as("viewer")
    _age_sessions(settings, settings.session_max_hours - 0.5)
    assert viewer.get("/api/auth/me").status_code == 200

    _age_sessions(settings, settings.session_max_hours + 0.1)
    # Busy right now (last_seen_at is now), but signed in too long ago.
    assert viewer.get("/api/auth/me").status_code == 401


def test_the_lifetime_is_configurable(settings):
    short = settings.model_copy(update={"session_max_hours": 1})
    from app.main import create_app
    from tests.conftest import add_user, open_session

    with TestClient(create_app(short)) as app_client:
        user = add_user(short, "viewer", "brief")
        app_client.cookies.set(SESSION_COOKIE, open_session(short, user["id"]))
        assert app_client.get("/api/auth/me").status_code == 200
        _age_sessions(short, 1.2)
        assert app_client.get("/api/auth/me").status_code == 401


def test_signing_in_prunes_sessions_past_their_lifetime(client_as, anon_client, settings):
    viewer = client_as("viewer", "old-timer")
    _age_sessions(settings, settings.session_max_hours + 1)
    assert viewer.get("/api/auth/me").status_code == 401

    from tests.conftest import add_user

    add_user(settings, "viewer", "newcomer")
    assert login(anon_client, "newcomer").status_code == 200
    conn = connect(settings.db_path)
    try:
        assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1
    finally:
        conn.close()


def test_the_ros_relay_refuses_a_session_past_its_lifetime(client, client_as, settings):
    """The relay finds its person through auth.signed_in, so the same limit applies."""
    fake = FakeRobot()
    client.app.state.ros_connect = fake  # type: ignore[attr-defined]
    robot = client.post("/api/robots", json={"name": "AMR-9", "bridge_url": "ws://10.0.0.9:8765"})
    viewer = client_as("viewer")
    _age_sessions(settings, settings.session_max_hours + 1)

    with (
        pytest.raises(WebSocketDisconnect) as caught,
        viewer.websocket_connect(f"/api/robots/{robot.json()['id']}/ros", headers=ORIGIN) as ws,
    ):
        ws.send_text(json.dumps({"op": "subscribe", "topic": "/map"}))
        ws.receive_text()
    assert caught.value.code == 4401
    assert fake.urls == []


# ── Password policy ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("password", "username", "why"),
    [
        ("a" * (PASSWORD_MIN - 1), None, "at least"),
        ("x" * (PASSWORD_MAX + 1), None, "at most"),
        ("Operator-7", "operator-7", "username"),
        ("zzzzzzzzzzzz", None, "repeated"),
        ("Password123", None, "guesser"),
        ("1234567890", None, "guesser"),
    ],
)
def test_the_policy_refuses(password, username, why):
    problem = password_problem(password, username)
    assert problem is not None and why in problem


def test_the_policy_accepts_a_reasonable_password():
    assert password_problem("pallet-bay-seven", "ops") is None


def test_creating_an_account_applies_the_policy(client):
    for password, field in (("too-short", "password"), ("qwertyuiop", "password")):
        refused = client.post(
            "/api/users", json={"username": "rina", "role": "viewer", "password": password}
        )
        assert refused.status_code == 422, password
        assert refused.json()["detail"][0]["loc"][-1] == field

    same = client.post(
        "/api/users", json={"username": "loader-one", "role": "viewer", "password": "Loader-One"}
    )
    assert same.status_code == 422
    assert same.json()["detail"]["field"] == "password"
    assert "username" in same.json()["detail"]["message"]


def test_an_admin_reset_applies_the_policy(client, client_as):
    operator = client_as("operator", "forklift-ops")
    for password in ("short-one", "password123", "FORKLIFT-OPS"):
        refused = client.patch(f"/api/users/{operator.user['id']}", json={"password": password})
        assert refused.status_code == 422, password
    # Nothing was changed, so the operator is still signed in.
    assert operator.get("/api/auth/me").status_code == 200


def test_changing_your_password_applies_the_policy(client_as):
    operator = client_as("operator", "dock-lead-2")
    for password in ("short-one", "welcome123", "Dock-Lead-2"):
        refused = operator.put(
            "/api/auth/password", json={"current_password": PASSWORD, "new_password": password}
        )
        assert refused.status_code == 422, password
        detail = refused.json()["detail"]
        field = detail["field"] if isinstance(detail, dict) else detail[0]["loc"][-1]
        assert field == "new_password"


def test_an_old_weak_password_still_signs_in(settings, anon_client):
    """The policy applies to passwords being set, never at sign-in."""
    conn = connect(settings.db_path)
    try:
        users_repo.create_user(
            conn,
            {"username": "veteran", "role": "viewer", "password_hash": hash_password("eight888")},
        )
    finally:
        conn.close()
    assert login(anon_client, "veteran", "eight888").status_code == 200


def test_the_command_line_admin_applies_the_policy(settings, monkeypatch, capsys):
    from app.db import migrate

    conn = connect(settings.db_path)
    migrate(conn)
    conn.close()

    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt="": "admin12345")
    assert cli.create_admin(settings, "root-admin", reset=False) == 2
    assert "guesser" in capsys.readouterr().err

    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt="": "Root-Admin")
    assert cli.create_admin(settings, "root-admin", reset=False) == 2

    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt="": "a-long-shift-phrase")
    assert cli.create_admin(settings, "root-admin", reset=False) == 0


def test_bootstrap_refuses_a_password_under_the_new_minimum(settings):
    from pydantic import SecretStr

    from app.main import create_app

    weak = "nine-char"
    assert len(weak) == PASSWORD_MIN - 1
    fresh = settings.model_copy(
        update={"bootstrap_user": "owner", "bootstrap_password": SecretStr(weak)}
    )
    with TestClient(create_app(fresh)) as app_client:
        assert login(app_client, "owner", weak).status_code == 401


# ── Change-password throttle ─────────────────────────────────────────────────


def test_wrong_current_passwords_are_throttled(client_as):
    operator = client_as("operator", "guessed-at")
    for _ in range(FAILURES_ALLOWED):
        wrong = operator.put(
            "/api/auth/password",
            json={"current_password": "not-it-at-all", "new_password": "pallet-bay-seven"},
        )
        assert wrong.status_code == 422

    paused = operator.put(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "pallet-bay-seven"},
    )
    assert paused.status_code == 429, "even the right password waits"
    assert int(paused.headers["Retry-After"]) > 0
    assert paused.json()["detail"]["field"] == "current_password"

    # Keyed on the account: someone else's change is unaffected.
    other = client_as("operator", "not-guessed")
    ok = other.put(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "pallet-bay-seven"},
    )
    assert ok.status_code == 204


def test_a_right_current_password_clears_the_count(client_as):
    operator = client_as("operator", "fumbler")
    for _ in range(FAILURES_ALLOWED - 1):
        operator.put(
            "/api/auth/password",
            json={"current_password": "not-it-at-all", "new_password": "pallet-bay-seven"},
        )
    assert (
        operator.put(
            "/api/auth/password",
            json={"current_password": PASSWORD, "new_password": "pallet-bay-seven"},
        ).status_code
        == 204
    )
    for _ in range(FAILURES_ALLOWED - 1):
        again = operator.put(
            "/api/auth/password",
            json={"current_password": "not-it-at-all", "new_password": "pallet-bay-eight"},
        )
        assert again.status_code == 422


# ── Throttle memory ──────────────────────────────────────────────────────────


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr(auth_api.time, "monotonic", fake)
    return fake


def test_looking_up_a_name_never_adds_it(clock):
    throttle = LoginThrottle()
    for n in range(100):
        assert throttle.retry_after(("10.0.0.1", f"name-{n}")) == 0
    assert len(throttle) == 0


def test_the_throttle_forgets_the_least_recently_failed_past_its_cap(clock):
    throttle = LoginThrottle(max_keys=3)
    for name in ("a", "b", "c"):
        throttle.fail(("ip", name))
    clock.now += 1
    throttle.fail(("ip", "a"))  # a is now the most recent
    throttle.fail(("ip", "d"))  # pushes out b, the least recently failed
    assert len(throttle) == 3
    assert throttle._failures.keys() == {("ip", "c"), ("ip", "a"), ("ip", "d")}


def test_expired_failures_are_swept(clock):
    throttle = LoginThrottle()
    for n in range(50):
        throttle.fail(("ip", f"name-{n}"))
    assert len(throttle) == 50
    clock.now += FAILURE_WINDOW_S + 1
    throttle.fail(("ip", "fresh"))
    assert len(throttle) == 1


def test_the_cap_does_not_weaken_the_throttle_for_one_key(clock):
    throttle = LoginThrottle(max_keys=10)
    key = ("10.0.0.1", "target")
    for _ in range(FAILURES_ALLOWED + 3):
        throttle.fail(key)
    assert throttle.retry_after(key) > 0
    assert len(throttle._failures[key]) == FAILURES_ALLOWED
