"""
Sign-in, sessions, roles and the audit trail.

The role tests are written as "who may do what" rather than per endpoint, so a
reader can check the matrix against what the plant expects in one place.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE
from app.db import connect
from tests.conftest import PASSWORD, add_user
from tests.test_missions import make_map, make_station


def login(client: TestClient, username: str, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


@pytest.fixture
def floor(client):
    """A map, two stations, a robot on that map, and a mission across them."""
    warehouse = make_map(client, "Warehouse A")
    a = make_station(client, warehouse, "Pickup A")
    b = make_station(client, warehouse, "Dropoff", type="drop", x=4.0)
    robot = client.post(
        "/api/robots", json={"name": "AMR-01", "bridge_url": "ws://10.0.0.1:8765"}
    ).json()
    client.put(f"/api/robots/{robot['id']}/map", json={"map_id": warehouse["id"]})
    mission = client.post(
        "/api/missions",
        json={
            "map_id": warehouse["id"],
            "name": "Shuttle",
            "steps": [
                {"station_id": a["id"], "task": "pick"},
                {"station_id": b["id"], "task": "drop"},
            ],
        },
    ).json()
    return {"map": warehouse, "robot": robot, "mission": mission, "station": a}


def audit_rows(settings) -> list[dict]:
    conn = connect(settings.db_path)
    try:
        return [dict(row) for row in conn.execute("SELECT * FROM audit_log ORDER BY id")]
    finally:
        conn.close()


# ── Signing in ────────────────────────────────────────────────────────────────


def test_sign_in_sets_an_httponly_cookie_and_me_answers(anon_client, settings):
    add_user(settings, "operator", "rifai")
    response = login(anon_client, "Rifai")  # names are case-insensitive

    assert response.status_code == 200
    assert response.json()["username"] == "rifai"
    assert response.json()["role"] == "operator"
    cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie

    me = anon_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["session_idle_minutes"] == settings.session_idle_minutes


def test_unknown_user_and_wrong_password_are_indistinguishable(anon_client, settings):
    add_user(settings, "viewer", "dina")
    wrong = login(anon_client, "dina", "not-the-password")
    unknown = login(anon_client, "nobody", "not-the-password")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_a_disabled_account_cannot_sign_in(client, anon_client, settings):
    user = add_user(settings, "operator", "leaver")
    client.patch(f"/api/users/{user['id']}", json={"disabled": True})

    assert login(anon_client, "leaver").status_code == 401


def test_repeated_failures_pause_sign_in_for_that_name(anon_client, settings):
    add_user(settings, "viewer", "guessme")
    for _ in range(5):
        assert login(anon_client, "guessme", "wrong-password").status_code == 401

    paused = login(anon_client, "guessme")  # even the right password waits
    assert paused.status_code == 429
    assert int(paused.headers["retry-after"]) > 0


def test_sign_out_ends_the_session(anon_client, settings):
    add_user(settings, "viewer", "dina")
    login(anon_client, "dina")
    token = anon_client.cookies.get(SESSION_COOKIE)

    assert anon_client.post("/api/auth/logout").status_code == 204
    # Replaying the old cookie does not bring the session back.
    anon_client.cookies.set(SESSION_COOKIE, token)
    assert anon_client.get("/api/auth/me").status_code == 401


def test_an_idle_session_expires(client_as, settings):
    viewer = client_as("viewer")
    conn = connect(settings.db_path)
    conn.execute(
        "UPDATE sessions SET last_seen_at = datetime('now', ?)",
        (f"-{settings.session_idle_minutes + 1} minutes",),
    )
    conn.close()

    assert viewer.get("/api/auth/me").status_code == 401


def test_changing_your_password_signs_out_your_other_browsers(client_as, settings):
    first = client_as("operator", "shift-lead")
    other = TestClient(first.app)
    login(other, "shift-lead")

    refused = first.put(
        "/api/auth/password",
        json={"current_password": "wrong-one", "new_password": "a-new-password"},
    )
    assert refused.status_code == 422
    assert refused.json()["detail"]["field"] == "current_password"

    changed = first.put(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "a-new-password"},
    )
    assert changed.status_code == 204
    assert first.get("/api/auth/me").status_code == 200, "the browser that changed it stays in"
    assert other.get("/api/auth/me").status_code == 401
    assert login(TestClient(first.app), "shift-lead", "a-new-password").status_code == 200


# ── Who may do what ───────────────────────────────────────────────────────────


def test_nobody_signed_in_may_not_change_anything(anon_client):
    # 401, not 403: the answer is "sign in", not "you are not allowed".
    response = anon_client.post(
        "/api/stations",
        json={"map_id": "x", "name": "A", "type": "pick", "x": 0, "y": 0, "yaw": 0},
    )
    assert response.status_code == 401
    assert anon_client.get("/api/auth/me").status_code == 401
    assert anon_client.get("/api/users").status_code == 401


def test_anonymous_agents_are_let_in_only_in_optional_development_mode(anon_client, floor):
    robot_id = floor["robot"]["id"]
    # By default nobody without credentials is taken for a robot.
    assert anon_client.app.state.settings.agent_auth == "required"
    assert anon_client.get(f"/api/robots/{robot_id}").status_code == 401
    assert (
        anon_client.put(f"/api/robots/{robot_id}/mode", json={"desired_mode": "nav"}).status_code
        == 401
    )

    # The development-only window: what an agent does on every sync, with no credentials.
    anon_client.app.state.settings.agent_auth = "optional"
    assert anon_client.get(f"/api/robots/{robot_id}").status_code == 200
    assert anon_client.get(f"/api/robots/{robot_id}/run").status_code == 200
    assert (
        anon_client.put(f"/api/robots/{robot_id}/mode", json={"desired_mode": "idle"}).status_code
        == 200
    )

    anon_client.app.state.settings.agent_auth = "required"
    assert anon_client.get(f"/api/robots/{robot_id}").status_code == 401
    assert (
        anon_client.put(f"/api/robots/{robot_id}/mode", json={"desired_mode": "nav"}).status_code
        == 401
    )


def test_a_viewer_can_look_but_not_touch(client_as, floor):
    viewer = client_as("viewer")
    assert viewer.get("/api/robots").status_code == 200
    assert viewer.get("/api/missions").status_code == 200

    run = viewer.post(
        "/api/runs", json={"mission_id": floor["mission"]["id"], "robot_id": floor["robot"]["id"]}
    )
    assert run.status_code == 403
    assert run.json()["detail"]["required_role"] == "operator"
    assert viewer.delete(f"/api/stations/{floor['station']['id']}").status_code == 403


def test_an_operator_runs_missions_but_does_not_edit_the_site(client_as, floor):
    operator = client_as("operator", "ops")
    run = operator.post(
        "/api/runs", json={"mission_id": floor["mission"]["id"], "robot_id": floor["robot"]["id"]}
    )
    assert run.status_code == 201
    assert run.json()["started_by"] == "ops"

    assert (
        operator.patch(f"/api/runs/{run.json()['id']}", json={"state": "canceled"}).status_code
        == 200
    )
    assert (
        operator.put(
            f"/api/robots/{floor['robot']['id']}/mode", json={"desired_mode": "idle"}
        ).status_code
        == 200
    )

    assert operator.delete(f"/api/stations/{floor['station']['id']}").status_code == 403
    assert (
        operator.patch(f"/api/missions/{floor['mission']['id']}", json={"name": "X"}).status_code
        == 403
    )
    assert operator.delete(f"/api/maps/{floor['map']['id']}").status_code == 403
    assert (
        operator.post(
            "/api/robots", json={"name": "AMR-02", "bridge_url": "ws://10.0.0.2:8765"}
        ).status_code
        == 403
    )
    assert operator.get("/api/users").status_code == 403
    assert operator.get("/api/audit").status_code == 403


# ── Accounts ──────────────────────────────────────────────────────────────────


def test_an_admin_creates_an_account_that_can_then_sign_in(client, anon_client):
    created = client.post(
        "/api/users",
        json={
            "username": "budi",
            "display_name": " Budi S ",
            "role": "operator",
            "password": "budi-pass-1",
        },
    )
    assert created.status_code == 201
    assert created.json()["display_name"] == "Budi S"
    assert "password" not in created.json() and "password_hash" not in created.json()

    duplicate = client.post(
        "/api/users", json={"username": "BUDI", "role": "viewer", "password": "another-pass"}
    )
    assert duplicate.status_code == 409

    assert login(anon_client, "budi", "budi-pass-1").json()["role"] == "operator"


@pytest.mark.parametrize("field", ["disabled", "role", "password"])
def test_a_null_user_field_is_refused_not_ignored(client, field):
    """``disabled: null`` used to become 0 and quietly re-enable the account."""
    created = client.post(
        "/api/users",
        json={"username": "nullcheck", "role": "viewer", "password": "a-long-enough-pass"},
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    assert client.patch(f"/api/users/{user_id}", json={"disabled": True}).status_code == 200

    response = client.patch(f"/api/users/{user_id}", json={field: None})

    assert response.status_code == 422
    users = {user["id"]: user for user in client.get("/api/users").json()}
    assert users[user_id]["disabled"] is True
    assert users[user_id]["role"] == "viewer"


@pytest.mark.parametrize("username", ["ab", "has space", "x" * 33, "semi;colon"])
def test_usernames_are_plain(client, username):
    response = client.post(
        "/api/users", json={"username": username, "role": "viewer", "password": "long-enough"}
    )
    assert response.status_code == 422


def test_short_passwords_are_refused(client):
    response = client.post(
        "/api/users", json={"username": "short", "role": "viewer", "password": "1234567"}
    )
    assert response.status_code == 422


def test_the_last_super_admin_cannot_be_demoted_disabled_or_removed(client, client_as):
    me = client.user  # the only super admin
    assert client.patch(f"/api/users/{me['id']}", json={"role": "operator"}).status_code == 409
    assert client.patch(f"/api/users/{me['id']}", json={"disabled": True}).status_code == 409
    assert client.delete(f"/api/users/{me['id']}").status_code == 409

    # A plain admin does not count: they cannot manage accounts.
    client_as("admin", "site-admin")
    assert client.patch(f"/api/users/{me['id']}", json={"role": "admin"}).status_code == 409

    # With a second super admin, demoting yourself is allowed.
    client_as("super_admin", "second")
    assert client.patch(f"/api/users/{me['id']}", json={"role": "operator"}).status_code == 200


def test_resetting_a_password_or_disabling_signs_the_account_out(client, client_as):
    operator = client_as("operator")
    assert operator.get("/api/auth/me").status_code == 200

    client.patch(f"/api/users/{operator.user['id']}", json={"password": "reset-by-admin"})
    assert operator.get("/api/auth/me").status_code == 401

    viewer = client_as("viewer")
    client.patch(f"/api/users/{viewer.user['id']}", json={"disabled": True})
    assert viewer.get("/api/auth/me").status_code == 401


# ── Audit ─────────────────────────────────────────────────────────────────────


def test_changes_are_recorded_with_who_made_them(client_as, floor, settings):
    operator = client_as("operator", "ops")
    operator.post(
        "/api/runs", json={"mission_id": floor["mission"]["id"], "robot_id": floor["robot"]["id"]}
    )
    operator.delete(f"/api/stations/{floor['station']['id']}")  # refused, still recorded

    rows = [row for row in audit_rows(settings) if row["username"] == "ops"]
    assert [(row["method"], row["path"], row["status"]) for row in rows] == [
        ("POST", "/api/runs", 201),
        ("DELETE", f"/api/stations/{floor['station']['id']}", 403),
    ]
    assert rows[0]["role"] == "operator"


def test_sign_in_attempts_are_recorded_with_the_name_tried(anon_client, settings):
    add_user(settings, "viewer", "dina")
    login(anon_client, "dina", "wrong-password")
    login(anon_client, "dina")
    anon_client.post("/api/auth/logout")

    rows = [
        (row["action"], row["username"], row["status"], row["detail"])
        for row in audit_rows(settings)
    ]
    assert rows == [
        ("login", "dina", 401, "bad password"),
        ("login", "dina", 200, None),
        ("logout", "dina", 204, None),
    ]


def test_agent_progress_reports_are_not_recorded(client, agent_for, floor, settings):
    agent = agent_for(client, floor["robot"]["id"])
    run = client.post(
        "/api/runs", json={"mission_id": floor["mission"]["id"], "robot_id": floor["robot"]["id"]}
    ).json()
    agent.patch(f"/api/runs/{run['id']}", json={"step_index": 1})
    agent.put(f"/api/robots/{floor['robot']['id']}/mode", json={"desired_mode": "idle"})

    agent_rows = [
        (row["method"], row["path"])
        for row in audit_rows(settings)
        if row["username"] == "agent:AMR-01"
    ]
    assert agent_rows == [("PUT", f"/api/robots/{floor['robot']['id']}/mode")]


def test_the_audit_trail_pages_newest_first_with_a_total(client):
    for name in ("one", "two", "three"):
        client.post(
            "/api/users", json={"username": name, "role": "viewer", "password": "long-enough"}
        )

    first = client.get("/api/audit", params={"limit": 2, "kind": "changes"}).json()
    assert first["total"] == 3
    assert [row["path"] for row in first["items"]] == ["/api/users", "/api/users"]
    second = client.get(
        "/api/audit",
        params={"limit": 2, "offset": 2, "kind": "changes", "upto_id": first["upto_id"]},
    ).json()
    assert len(second["items"]) == 1
    assert second["items"][0]["id"] < first["items"][-1]["id"]


def test_a_pinned_reading_does_not_shift_when_records_arrive(client):
    for name in ("one", "two"):
        client.post(
            "/api/users", json={"username": name, "role": "viewer", "password": "long-enough"}
        )
    first = client.get("/api/audit", params={"limit": 1, "kind": "changes"}).json()
    client.post(
        "/api/users", json={"username": "late", "role": "viewer", "password": "long-enough"}
    )

    pinned = client.get(
        "/api/audit",
        params={"limit": 1, "offset": 1, "kind": "changes", "upto_id": first["upto_id"]},
    ).json()
    assert pinned["total"] == 2, "the record written meanwhile is not counted"
    assert pinned["items"][0]["id"] < first["items"][0]["id"]


def test_the_audit_trail_filters(client, anon_client, settings):
    add_user(settings, "viewer", "dina")
    login(anon_client, "dina", "wrong-password")
    login(anon_client, "dina")
    client.post(
        "/api/users", json={"username": "ops_1", "role": "viewer", "password": "long-enough"}
    )

    def total(**params):
        return client.get("/api/audit", params=params).json()["total"]

    assert total(kind="sign-ins") == 2
    assert total(kind="refused") == 1
    assert total(kind="changes") == 1
    assert total(q="DINA") == 2, "search ignores case"
    # % and _ are characters to find, not wildcards: "a_b" does not match "aXb".
    login(anon_client, "a_b", "whatever-pass")
    login(anon_client, "aXb", "whatever-pass")
    assert total(q="a_b") == 1
    assert total(q="a%b") == 0
    assert total(since="2999-01-01T00:00:00Z") == 0
    assert total(until="2999-01-01T00:00:00+07:00") >= 3


def test_the_audit_trail_exports_csv_without_live_formulas(client, anon_client):
    login(anon_client, "=HYPERLINK(evil)", "whatever-pass")
    response = client.get("/api/audit/export.csv", params={"kind": "sign-ins"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("id,at_utc,username")
    assert "'=HYPERLINK(evil)" in lines[1]


# ── First admin ───────────────────────────────────────────────────────────────


def test_create_admin_makes_the_first_account(settings, monkeypatch, anon_client):
    from app.__main__ import create_admin

    answers = iter(["first-admin-pass", "first-admin-pass"])
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": next(answers))

    assert create_admin(settings, "boss", reset=False) == 0
    assert login(anon_client, "boss", "first-admin-pass").json()["role"] == "super_admin"

    answers = iter(["first-admin-pass", "first-admin-pass"])
    assert create_admin(settings, "boss", reset=False) == 1, "never silently overwrites"


# ── Super admin, bootstrap and temporary passwords ───────────────────────────


def test_an_admin_edits_the_site_but_not_people(client_as, floor):
    admin = client_as("admin")
    assert (
        admin.patch(f"/api/stations/{floor['station']['id']}", json={"name": "P-A"}).status_code
        == 200
    )
    assert admin.get("/api/users").status_code == 403
    assert admin.get("/api/audit").status_code == 403
    refused = admin.post(
        "/api/users", json={"username": "sneaky", "role": "super_admin", "password": "long-enough"}
    )
    assert refused.status_code == 403
    assert refused.json()["detail"]["required_role"] == "super_admin"


def _fresh_app(settings, **overrides):
    from app.main import create_app

    return TestClient(create_app(settings.model_copy(update=overrides)))


def test_bootstrap_creates_a_super_admin_on_an_empty_database(settings):
    from pydantic import SecretStr

    with _fresh_app(
        settings, bootstrap_user="owner", bootstrap_password=SecretStr("first-pass-1")
    ) as fresh:
        signed = login(fresh, "owner", "first-pass-1")
        assert signed.status_code == 200
        assert signed.json()["role"] == "super_admin"
        assert signed.json()["must_change_password"] is True


def test_bootstrap_is_ignored_once_anyone_exists(settings):
    from pydantic import SecretStr

    with _fresh_app(settings):
        pass  # migrate
    add_user(settings, "viewer", "already-here")
    with _fresh_app(
        settings, bootstrap_user="owner", bootstrap_password=SecretStr("first-pass-1")
    ) as fresh:
        assert login(fresh, "owner", "first-pass-1").status_code == 401


def test_bootstrap_refuses_a_short_password(settings):
    from pydantic import SecretStr

    with _fresh_app(
        settings, bootstrap_user="owner", bootstrap_password=SecretStr("short")
    ) as fresh:
        assert login(fresh, "owner", "short").status_code == 401


def test_a_temporary_password_allows_nothing_but_replacing_it(client, anon_client):
    client.post(
        "/api/users", json={"username": "newbie", "role": "operator", "password": "temp-pass-1"}
    )
    signed = login(anon_client, "newbie", "temp-pass-1")
    assert signed.json()["must_change_password"] is True

    blocked = anon_client.get("/api/robots")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "password_change_required"
    assert anon_client.get("/api/auth/me").json()["must_change_password"] is True

    changed = anon_client.put(
        "/api/auth/password",
        json={"current_password": "temp-pass-1", "new_password": "my-own-pass"},
    )
    assert changed.status_code == 204
    assert anon_client.get("/api/auth/me").json()["must_change_password"] is False
    assert anon_client.get("/api/robots").status_code == 200


def test_a_reset_is_temporary_unless_you_reset_yourself(client, client_as):
    operator = client_as("operator", "ops")
    client.patch(f"/api/users/{operator.user['id']}", json={"password": "reset-by-boss"})
    assert next(u for u in client.get("/api/users").json() if u["username"] == "ops")[
        "must_change_password"
    ]

    client.patch(f"/api/users/{client.user['id']}", json={"password": "my-own-new-one"})
    me = next(u for u in client.get("/api/users").json() if u["id"] == client.user["id"])
    assert me["must_change_password"] is False
