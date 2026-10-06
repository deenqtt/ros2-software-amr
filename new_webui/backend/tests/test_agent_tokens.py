"""
Robot agent credentials.

An agent proves which robot it is with a bearer token an admin minted for that
robot, and may then act for that robot only. Nobody is a robot merely by not
being signed in — except in local development, when asked for explicitly.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE
from app.config import Settings
from app.db import connect
from app.main import create_app
from app.security import hash_token
from tests.conftest import add_user, open_session
from tests.test_missions import MAP_YAML, make_map, make_station, pgm


@pytest.fixture
def site(client):
    """One map, two robots on it, a mission, and a live run on each robot."""
    warehouse = make_map(client, "Warehouse A")
    a = make_station(client, warehouse, "Pickup A")
    b = make_station(client, warehouse, "Dropoff", type="drop", x=4.0)
    robots = {}
    for name, host in (("AMR-01", "10.0.0.1"), ("AMR-02", "10.0.0.2")):
        robot = client.post(
            "/api/robots", json={"name": name, "bridge_url": f"ws://{host}:8765"}
        ).json()
        client.put(f"/api/robots/{robot['id']}/map", json={"map_id": warehouse["id"]})
        robots[name] = robot
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
    runs = {
        name: client.post(
            "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
        ).json()
        for name, robot in robots.items()
    }
    return {"map": warehouse, "robots": robots, "mission": mission, "runs": runs}


def map_files(fill: int = 0) -> dict:
    return {
        "yaml_file": ("map.yaml", MAP_YAML, "application/x-yaml"),
        "image_file": ("survey.pgm", pgm(fill=fill), "image/x-portable-graymap"),
    }


def agent_routes(site) -> list[tuple[str, str, dict]]:
    """Every endpoint an agent uses: (method, path, request kwargs)."""
    robot_id = site["robots"]["AMR-01"]["id"]
    map_id = site["map"]["id"]
    return [
        ("GET", f"/api/robots/{robot_id}", {}),
        ("GET", f"/api/robots/{robot_id}/run", {}),
        ("PUT", f"/api/robots/{robot_id}/mode", {"json": {"desired_mode": "idle"}}),
        ("PUT", f"/api/robots/{robot_id}/map", {"json": {"map_id": map_id}}),
        ("PATCH", f"/api/runs/{site['runs']['AMR-01']['id']}", {"json": {"step_index": 1}}),
        ("POST", "/api/maps", {"data": {"name": "Survey"}, "files": map_files(254)}),
        ("GET", "/api/maps", {}),
        ("GET", f"/api/maps/{map_id}", {}),
        ("GET", f"/api/maps/{map_id}/files/yaml", {}),
        ("GET", "/api/stations", {}),
        ("GET", "/api/zones", {}),
    ]


def audit_rows(settings) -> list[dict]:
    conn = connect(settings.db_path)
    try:
        return [dict(row) for row in conn.execute("SELECT * FROM audit_log ORDER BY id")]
    finally:
        conn.close()


# ── Refusals ──────────────────────────────────────────────────────────────────


def test_agent_auth_is_required_by_default():
    assert Settings(_env_file=None).agent_auth == "required"


def test_no_credentials_are_refused_on_every_agent_route(anon_client, site):
    for method, path, kwargs in agent_routes(site):
        response = anon_client.request(method, path, **kwargs)
        assert response.status_code == 401, (method, path)


def test_an_invalid_bearer_token_is_refused_on_every_agent_route(anon_client, site):
    for token in ("not-a-real-token", ""):
        headers = {"Authorization": f"Bearer {token}"}
        for method, path, kwargs in agent_routes(site):
            response = anon_client.request(method, path, headers=headers, **kwargs)
            assert response.status_code == 401, (token, method, path)


def test_an_invalid_bearer_does_not_fall_back_even_in_optional_mode(anon_client, site):
    anon_client.app.state.settings.agent_auth = "optional"
    robot_id = site["robots"]["AMR-01"]["id"]
    response = anon_client.put(
        f"/api/robots/{robot_id}/mode",
        json={"desired_mode": "idle"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


def test_an_invalid_bearer_is_refused_even_with_a_valid_cookie(client_as, site):
    operator = client_as("operator")
    robot_id = site["robots"]["AMR-01"]["id"]
    response = operator.put(
        f"/api/robots/{robot_id}/mode",
        json={"desired_mode": "idle"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


def test_a_stale_or_invalid_cookie_is_never_an_agent(anon_client, settings, site):
    anon_client.app.state.settings.agent_auth = "optional"

    # A session that existed once, then ended.
    user = add_user(settings, "viewer")
    stale = open_session(settings, user["id"])
    conn = connect(settings.db_path)
    try:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(stale),))
        conn.commit()
    finally:
        conn.close()

    for cookie in ("forged-cookie", stale):
        browser = TestClient(anon_client.app)
        browser.cookies.set(SESSION_COOKIE, cookie)
        for method, path, kwargs in agent_routes(site):
            response = browser.request(method, path, **kwargs)
            assert response.status_code == 401, (cookie, method, path)


def test_a_non_bearer_authorization_header_is_not_an_anonymous_agent(anon_client, site):
    anon_client.app.state.settings.agent_auth = "optional"
    robot_id = site["robots"]["AMR-01"]["id"]
    response = anon_client.get(
        f"/api/robots/{robot_id}", headers={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    assert response.status_code == 401


def test_optional_agent_auth_refuses_to_start_in_production(tmp_path):
    settings = Settings(
        _env_file=None,
        env="production",
        agent_auth="optional",
        db_path=tmp_path / "amr.db",
        maps_dir=tmp_path / "maps",
        cors_origins=["http://amr.example.local"],
    )
    with pytest.raises(ValueError, match="AMR_AGENT_AUTH"):
        settings.validate_for_runtime()
    with pytest.raises(ValueError, match="AMR_AGENT_AUTH"):
        create_app(settings)


def test_optional_development_mode_still_lets_an_anonymous_agent_in(anon_client, site):
    anon_client.app.state.settings.agent_auth = "optional"
    for method, path, kwargs in agent_routes(site):
        response = anon_client.request(method, path, **kwargs)
        assert response.status_code < 300, (method, path, response.text)


def test_optional_mode_is_ignored_in_production_even_if_set_after_startup(anon_client, site):
    # Belt and braces: the guard itself checks the environment too.
    anon_client.app.state.settings.agent_auth = "optional"
    anon_client.app.state.settings.env = "production"
    robot_id = site["robots"]["AMR-01"]["id"]
    assert anon_client.get(f"/api/robots/{robot_id}").status_code == 401


# ── A valid token ─────────────────────────────────────────────────────────────


def test_a_valid_token_acts_for_its_own_robot(client, agent_for, site):
    robot = site["robots"]["AMR-01"]
    agent = agent_for(client, robot["id"])

    for method, path, kwargs in agent_routes(site):
        response = agent.request(method, path, **kwargs)
        assert response.status_code < 300, (method, path, response.text)

    mode = agent.put(f"/api/robots/{robot['id']}/mode", json={"desired_mode": "map"})
    assert mode.status_code == 200
    assert mode.json()["desired_mode"] == "map"

    assigned = agent.put(f"/api/robots/{robot['id']}/map", json={"map_id": site["map"]["id"]})
    assert assigned.status_code == 200

    plan = agent.get(f"/api/robots/{robot['id']}/run")
    assert plan.status_code == 200
    assert plan.json()["id"] == site["runs"]["AMR-01"]["id"]

    run_id = site["runs"]["AMR-01"]["id"]
    assert agent.patch(f"/api/runs/{run_id}", json={"lap": 1}).status_code == 200
    ended = agent.patch(f"/api/runs/{run_id}", json={"state": "done"})
    assert ended.status_code == 200
    assert ended.json()["state"] == "done"


def test_an_agent_publishes_maps_as_its_own_robot(client, agent_for, site):
    mine = site["robots"]["AMR-01"]
    other = site["robots"]["AMR-02"]
    agent = agent_for(client, mine["id"])

    created = agent.post("/api/maps", data={"name": "Survey"}, files=map_files(254))
    assert created.status_code == 201
    assert created.json()["created_by_robot_id"] == mine["id"]

    # Naming another robot does not make it that robot's survey.
    spoofed = agent.post(
        "/api/maps", data={"name": "Survey 2", "robot_id": other["id"]}, files=map_files()
    )
    assert spoofed.status_code == 201
    assert spoofed.json()["created_by_robot_id"] == mine["id"]


def test_an_agent_cannot_act_for_another_robot(client, agent_for, site):
    agent = agent_for(client, site["robots"]["AMR-01"]["id"])
    other = site["robots"]["AMR-02"]

    assert (
        agent.put(f"/api/robots/{other['id']}/mode", json={"desired_mode": "idle"}).status_code
        == 403
    )
    assert agent.put(f"/api/robots/{other['id']}/map", json={"map_id": None}).status_code == 403
    assert agent.get(f"/api/robots/{other['id']}/run").status_code == 403
    other_run = site["runs"]["AMR-02"]["id"]
    assert agent.patch(f"/api/runs/{other_run}", json={"step_index": 1}).status_code == 403
    assert agent.patch(f"/api/runs/{other_run}", json={"state": "canceled"}).status_code == 403

    # Nothing changed on the other robot.
    after = client.get(f"/api/robots/{other['id']}").json()
    assert after["desired_mode"] == "nav"
    assert after["active_map_id"] == site["map"]["id"]
    assert client.get(f"/api/runs/{other_run}").json()["state"] != "canceled"


def test_a_token_never_stands_in_for_a_person(client, agent_for, site):
    robot_id = site["robots"]["AMR-01"]["id"]
    agent = agent_for(client, robot_id)

    assert agent.get("/api/auth/me").status_code == 401
    assert agent.get("/api/users").status_code == 401
    assert agent.get("/api/audit").status_code == 401
    assert agent.delete(f"/api/maps/{site['map']['id']}").status_code == 401
    assert (
        agent.post(
            "/api/runs",
            json={"mission_id": site["mission"]["id"], "robot_id": robot_id},
        ).status_code
        == 401
    )
    assert agent.patch(f"/api/robots/{robot_id}", json={"name": "Renamed"}).status_code == 401
    # Nor can an agent mint or revoke credentials, its own included.
    assert agent.post(f"/api/robots/{robot_id}/agent-token").status_code == 401
    assert agent.delete(f"/api/robots/{robot_id}/agent-token").status_code == 401


# ── Minting, rotating, revoking ───────────────────────────────────────────────


def test_only_an_admin_mints_a_token(client_as, site):
    robot_id = site["robots"]["AMR-01"]["id"]
    assert client_as("viewer").post(f"/api/robots/{robot_id}/agent-token").status_code == 403
    assert client_as("operator").post(f"/api/robots/{robot_id}/agent-token").status_code == 403
    assert client_as("viewer").delete(f"/api/robots/{robot_id}/agent-token").status_code == 403

    minted = client_as("admin").post(f"/api/robots/{robot_id}/agent-token")
    assert minted.status_code == 201
    body = minted.json()
    assert set(body) == {"token", "created_at"}
    assert len(body["token"]) >= 40
    assert body["created_at"]
    assert "no-store" in minted.headers["cache-control"]


def test_minting_for_an_unknown_robot_is_404(client):
    assert client.post("/api/robots/nope/agent-token").status_code == 404
    assert client.delete("/api/robots/nope/agent-token").status_code == 404


def test_minting_again_rotates_the_token(client, agent_for, site):
    robot_id = site["robots"]["AMR-01"]["id"]
    old = agent_for(client, robot_id)
    assert old.get(f"/api/robots/{robot_id}").status_code == 200

    new = agent_for(client, robot_id)
    assert new.token != old.token  # type: ignore[attr-defined]
    assert old.get(f"/api/robots/{robot_id}").status_code == 401
    assert new.get(f"/api/robots/{robot_id}").status_code == 200


def test_revoking_shuts_the_agent_out(client, agent_for, site):
    robot_id = site["robots"]["AMR-01"]["id"]
    agent = agent_for(client, robot_id)
    assert client.delete(f"/api/robots/{robot_id}/agent-token").status_code == 204
    assert agent.get(f"/api/robots/{robot_id}").status_code == 401
    robot = client.get(f"/api/robots/{robot_id}").json()
    assert robot["agent_token_set"] is False
    assert robot["agent_token_created_at"] is None


def test_the_token_and_its_hash_never_leave_the_server(client, agent_for, settings, site):
    robot_id = site["robots"]["AMR-01"]["id"]
    assert client.get(f"/api/robots/{robot_id}").json()["agent_token_set"] is False

    agent = agent_for(client, robot_id)
    token = agent.token  # type: ignore[attr-defined]
    stored_hash = hash_token(token)
    agent.put(f"/api/robots/{robot_id}/mode", json={"desired_mode": "idle"})

    robot = client.get(f"/api/robots/{robot_id}").json()
    assert robot["agent_token_set"] is True
    assert robot["agent_token_created_at"]
    assert "agent_token_hash" not in robot

    for response in (
        client.get("/api/robots"),
        client.get(f"/api/robots/{robot_id}"),
        agent.get(f"/api/robots/{robot_id}"),
        client.patch(f"/api/robots/{robot_id}", json={"serial": "SN-1"}),
    ):
        assert token not in response.text
        assert stored_hash not in response.text

    for row in audit_rows(settings):
        for value in row.values():
            assert token not in str(value)
            assert stored_hash not in str(value)


# ── Audit ─────────────────────────────────────────────────────────────────────


def test_agent_changes_are_recorded_under_the_robots_name(client, agent_for, settings, site):
    robot_id = site["robots"]["AMR-01"]["id"]
    run_id = site["runs"]["AMR-01"]["id"]
    agent = agent_for(client, robot_id)

    agent.put(f"/api/robots/{robot_id}/mode", json={"desired_mode": "idle"})
    agent.patch(f"/api/runs/{run_id}", json={"step_index": 1})  # progress: not recorded
    agent.patch(f"/api/runs/{run_id}", json={"reached_lap": 1, "reached_index": 0})
    agent.patch(f"/api/runs/{run_id}", json={"state": "failed", "detail": "blocked"})
    agent.put(f"/api/robots/{site['robots']['AMR-02']['id']}/mode", json={"desired_mode": "idle"})

    rows = [row for row in audit_rows(settings) if row["username"] == "agent:AMR-01"]
    assert [(row["method"], row["path"], row["status"]) for row in rows] == [
        ("PUT", f"/api/robots/{robot_id}/mode", 200),
        ("PATCH", f"/api/runs/{run_id}", 200),
        ("PUT", f"/api/robots/{site['robots']['AMR-02']['id']}/mode", 403),
    ]
    assert all(row["user_id"] is None and row["role"] is None for row in rows)


# ── People are unchanged ──────────────────────────────────────────────────────


def test_people_keep_their_roles_on_agent_routes(client_as, site):
    robot_id = site["robots"]["AMR-01"]["id"]
    run_id = site["runs"]["AMR-01"]["id"]

    viewer = client_as("viewer")
    assert viewer.get(f"/api/robots/{robot_id}").status_code == 200
    assert viewer.get(f"/api/robots/{robot_id}/run").status_code == 200
    assert (
        viewer.put(f"/api/robots/{robot_id}/mode", json={"desired_mode": "idle"}).status_code == 403
    )
    assert viewer.put(f"/api/robots/{robot_id}/map", json={"map_id": None}).status_code == 403
    assert viewer.patch(f"/api/runs/{run_id}", json={"state": "stopping"}).status_code == 403
    assert viewer.post("/api/maps", data={"name": "X"}, files=map_files()).status_code == 403

    operator = client_as("operator")
    assert (
        operator.put(f"/api/robots/{robot_id}/mode", json={"desired_mode": "idle"}).status_code
        == 200
    )
    assert operator.put(f"/api/robots/{robot_id}/map", json={"map_id": None}).status_code == 403
    assert operator.patch(f"/api/runs/{run_id}", json={"state": "stopping"}).status_code == 200

    admin = client_as("admin")
    # People are not bound to a robot: one admin manages the whole fleet.
    for robot in site["robots"].values():
        assert (
            admin.put(f"/api/robots/{robot['id']}/map", json={"map_id": site["map"]["id"]})
        ).status_code == 200
    created = admin.post("/api/maps", data={"name": "Hand upload"}, files=map_files())
    assert created.status_code == 201
    assert created.json()["created_by_robot_id"] is None
