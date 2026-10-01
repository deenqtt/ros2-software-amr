"""
Missions and runs.

A mission is a route; a run is one execution of it. Most of these pin decisions
rather than mechanics: looping belongs to the run, a robot has one live run, and
a route is refused when it names a station from another map — each of which the
previous design got wrong in a way that only showed up on the floor.
"""

from __future__ import annotations

import pytest

MAP_YAML = b"""image: warehouse.pgm
resolution: 0.05
origin: [-1.5, -2.5, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
"""

OCCUPIED, FREE = 0, 254


def pgm(width: int = 12, height: int = 7, fill: int = OCCUPIED) -> bytes:
    return f"P5\n{width} {height}\n255\n".encode() + bytes([fill]) * (width * height)


def make_map(client, name: str, fill: int = OCCUPIED) -> dict:
    return client.post(
        "/api/maps",
        data={"name": name},
        files={
            "yaml_file": ("map.yaml", MAP_YAML, "application/x-yaml"),
            "image_file": ("warehouse.pgm", pgm(fill=fill), "image/x-portable-graymap"),
        },
    ).json()


def make_station(client, stored_map: dict, name: str, **overrides) -> dict:
    return client.post(
        "/api/stations",
        json={
            "map_id": stored_map["id"],
            "name": name,
            "type": "pick",
            "x": 1.0,
            "y": 2.0,
            "yaw": 0.0,
            **overrides,
        },
    ).json()


@pytest.fixture
def warehouse(client):
    return make_map(client, "Warehouse A")


@pytest.fixture
def stations(client, warehouse):
    return [
        make_station(client, warehouse, "Pickup A"),
        make_station(client, warehouse, "Dropoff", type="drop", x=4.0),
    ]


@pytest.fixture
def robot(client, warehouse):
    created = client.post(
        "/api/robots", json={"name": "AMR-01", "bridge_url": "ws://10.0.0.1:8765"}
    ).json()
    client.put(f"/api/robots/{created['id']}/map", json={"map_id": warehouse["id"]})
    return client.get(f"/api/robots/{created['id']}").json()


def route(warehouse, stations, name: str = "Shuttle", **overrides) -> dict:
    return {
        "map_id": warehouse["id"],
        "name": name,
        "steps": [
            {"station_id": stations[0]["id"], "task": "pick"},
            {"station_id": stations[1]["id"], "task": "drop"},
        ],
        **overrides,
    }


# ── Routes ────────────────────────────────────────────────────────────────────


def test_registry_starts_empty(client):
    assert client.get("/api/missions").json() == []


def test_steps_are_numbered_from_their_position(client, warehouse, stations):
    """The client sends what the editor shows; ordinals are the server's job."""
    body = client.post("/api/missions", json=route(warehouse, stations)).json()

    assert [step["ordinal"] for step in body["steps"]] == [1, 2]
    assert [step["task"] for step in body["steps"]] == ["pick", "drop"]


def test_a_route_may_visit_the_same_station_twice(client, warehouse, stations):
    """Pick at A, drop at B, come back to A. Nothing about that is unusual."""
    payload = route(warehouse, stations)
    payload["steps"].append({"station_id": stations[0]["id"], "task": "none"})

    body = client.post("/api/missions", json=payload).json()

    assert len(body["steps"]) == 3


def test_a_step_naming_another_maps_station_is_refused(client, warehouse, stations):
    """
    It would pass the foreign key and fail on the robot, at the point where the
    coordinates land somewhere that does not exist in this map's frame.
    """
    other_map = make_map(client, "Loading Bay", fill=FREE)
    stranger = make_station(client, other_map, "Elsewhere")

    response = client.post(
        "/api/missions",
        json={
            "map_id": warehouse["id"],
            "name": "Mixed",
            "steps": [{"station_id": stranger["id"], "task": "pick"}],
        },
    )

    assert response.status_code == 422
    assert "another map" in response.json()["detail"]


def test_a_step_naming_a_missing_station_is_refused(client, warehouse):
    response = client.post(
        "/api/missions",
        json={
            "map_id": warehouse["id"],
            "name": "Broken",
            "steps": [{"station_id": "ghost", "task": "pick"}],
        },
    )
    assert response.status_code == 404
    assert "Step 1" in response.json()["detail"]


def test_names_are_unique_per_map(client, warehouse, stations):
    client.post("/api/missions", json=route(warehouse, stations))
    response = client.post("/api/missions", json=route(warehouse, stations))

    assert response.status_code == 409
    assert response.json()["detail"]["field"] == "name"


def test_the_list_carries_step_counts_without_the_steps(client, warehouse, stations):
    client.post("/api/missions", json=route(warehouse, stations))

    rows = client.get("/api/missions").json()

    assert rows[0]["step_count"] == 2
    assert "steps" not in rows[0]


def test_the_list_carries_the_route_in_visiting_order(client, warehouse, stations):
    """Enough to preview "Pickup A → Dropoff → Pickup A" without fetching steps."""
    steps = [
        {"station_id": stations[0]["id"], "task": "pick"},
        {"station_id": stations[1]["id"], "task": "drop"},
        {"station_id": stations[0]["id"], "task": "none"},
    ]
    client.post("/api/missions", json=route(warehouse, stations, steps=steps))
    client.post("/api/missions", json=route(warehouse, stations, name="Empty", steps=[]))

    rows = {row["name"]: row for row in client.get("/api/missions").json()}

    assert rows["Shuttle"]["station_ids"] == [
        stations[0]["id"],
        stations[1]["id"],
        stations[0]["id"],
    ]
    assert rows["Empty"]["station_ids"] == []


def test_reordering_replaces_the_whole_list(client, warehouse, stations):
    """
    The thing being edited is an order. Patching rows individually means
    shuffling ordinals past a unique index with every intermediate state legal.
    """
    created = client.post("/api/missions", json=route(warehouse, stations)).json()

    reordered = client.patch(
        f"/api/missions/{created['id']}",
        json={
            "steps": [
                {"station_id": stations[1]["id"], "task": "drop"},
                {"station_id": stations[0]["id"], "task": "pick"},
            ]
        },
    ).json()

    assert [step["station_id"] for step in reordered["steps"]] == [
        stations[1]["id"],
        stations[0]["id"],
    ]
    assert [step["ordinal"] for step in reordered["steps"]] == [1, 2]


def test_renaming_leaves_the_steps_alone(client, warehouse, stations):
    created = client.post("/api/missions", json=route(warehouse, stations)).json()

    renamed = client.patch(f"/api/missions/{created['id']}", json={"name": "Night run"}).json()

    assert renamed["name"] == "Night run"
    assert len(renamed["steps"]) == 2


def test_more_steps_than_the_cap_are_refused(client, warehouse, stations):
    payload = route(warehouse, stations)
    payload["steps"] = [{"station_id": stations[0]["id"], "task": "none"}] * 51
    assert client.post("/api/missions", json=payload).status_code == 422


def test_deleting_a_mission_takes_its_steps(client, warehouse, stations):
    created = client.post("/api/missions", json=route(warehouse, stations)).json()

    assert client.delete(f"/api/missions/{created['id']}").status_code == 204
    assert client.get(f"/api/missions/{created['id']}").status_code == 404


def test_a_station_a_mission_uses_cannot_be_deleted(client, warehouse, stations):
    """
    Otherwise the step survives pointing at nothing and fails on the robot with
    "Unknown station_id", in front of whoever is standing there.
    """
    client.post("/api/missions", json=route(warehouse, stations, name="Shuttle"))

    response = client.delete(f"/api/stations/{stations[0]['id']}")

    assert response.status_code == 409
    assert response.json()["detail"]["missions"] == ["Shuttle"]


def test_a_map_a_mission_uses_cannot_be_deleted(client, warehouse, stations):
    """
    Nothing is assigned to the map, so only the mission stands in the way — and
    the refusal has to say so rather than surfacing a constraint error as a
    server fault.
    """
    client.post("/api/missions", json=route(warehouse, stations, name="Shuttle"))

    response = client.delete(f"/api/maps/{warehouse['id']}")

    assert response.status_code == 409
    assert response.json()["detail"]["missions"] == ["Shuttle"]


# ── Runs ──────────────────────────────────────────────────────────────────────


def test_dispatch_records_the_route_name_alongside_its_id(client, warehouse, stations, robot):
    """History has to stay readable after the route is deleted."""
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()

    run = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()

    assert run["mission_name"] == "Shuttle"
    assert run["state"] == "running"
    assert (run["lap"], run["step_index"]) == (1, 0)


def test_looping_is_chosen_at_dispatch_not_stored_on_the_route(client, warehouse, stations, robot):
    """
    The same route is sometimes a one-off and sometimes a shift of shuttling.
    Storing `loop` on the route forces two near-identical routes that drift.
    """
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()

    run = client.post(
        "/api/runs",
        json={
            "mission_id": mission["id"],
            "robot_id": robot["id"],
            "mode": "laps",
            "laps_target": 10,
        },
    ).json()

    assert (run["mode"], run["laps_target"]) == ("laps", 10)
    # Nothing about looping reached the route itself.
    assert "mode" not in client.get(f"/api/missions/{mission['id']}").json()


def test_laps_without_a_count_is_refused(client, warehouse, stations, robot):
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()

    response = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"], "mode": "laps"}
    )

    assert response.status_code == 422


def test_a_count_without_a_looping_mode_is_refused(client, warehouse, stations, robot):
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()

    response = client.post(
        "/api/runs",
        json={
            "mission_id": mission["id"],
            "robot_id": robot["id"],
            "mode": "once",
            "laps_target": 5,
        },
    )

    assert response.status_code == 422


def test_a_busy_robot_is_refused_by_name(client, warehouse, stations, robot):
    """
    No queue. A mission is already an ordered list, so "do A then B" is one
    mission — and a clear refusal beats a scheduler nobody can reason about.
    """
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    client.post("/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]})

    response = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    )

    assert response.status_code == 409
    assert response.json()["detail"]["mission"] == "Shuttle"


def test_a_finished_run_frees_the_robot(client, warehouse, stations, robot):
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    first = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()

    client.patch(f"/api/runs/{first['id']}", json={"state": "done"})

    assert (
        client.post(
            "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
        ).status_code
        == 201
    )


def test_a_terminal_run_is_stamped_with_an_end_time(client, warehouse, stations, robot):
    """A finished run with no end time looks like one still going."""
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    run = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()
    assert run["ended_at"] is None

    finished = client.patch(f"/api/runs/{run['id']}", json={"state": "failed"}).json()

    assert finished["ended_at"] is not None


def test_an_arrival_is_recorded_and_stamped_by_the_server(client, warehouse, stations, robot):
    """`step_index` is where the robot is going; an arrival is reported on its own."""
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    run = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()
    assert run["reached_index"] is None
    assert run["reached_at"] is None

    reached = client.patch(
        f"/api/runs/{run['id']}", json={"reached_lap": 1, "reached_index": 0}
    ).json()

    assert reached["reached_lap"] == 1
    assert reached["reached_index"] == 0
    assert reached["reached_at"] is not None
    # An arrival is not a terminal state.
    assert reached["state"] == "running"
    assert reached["ended_at"] is None


def test_a_canceled_run_cannot_be_overwritten(client, warehouse, stations, robot):
    """
    The agent finishing its lap used to write `done` over a run the operator
    had canceled, so history said an abandoned route had been completed.
    """
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    run = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()
    client.patch(f"/api/runs/{run['id']}", json={"state": "canceled"})

    response = client.patch(f"/api/runs/{run['id']}", json={"state": "done"})

    assert response.status_code == 409
    assert response.json()["detail"]["state"] == "canceled"
    assert client.get(f"/api/runs/{run['id']}").json()["state"] == "canceled"


def test_an_ended_run_takes_no_more_progress(client, warehouse, stations, robot):
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    run = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()
    client.patch(f"/api/runs/{run['id']}", json={"state": "done"})

    response = client.patch(
        f"/api/runs/{run['id']}", json={"reached_lap": 1, "reached_index": 1}
    )

    assert response.status_code == 409


def test_stopping_is_not_terminal(client, warehouse, stations, robot):
    """
    "Stop after this lap" has to leave the run live: halting mid-lap can leave a
    robot holding a payload it has not delivered.
    """
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    run = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()

    stopping = client.patch(f"/api/runs/{run['id']}", json={"state": "stopping"}).json()

    assert stopping["ended_at"] is None
    # Still holds the robot, so nothing else can be dispatched to it mid-lap.
    assert (
        client.post(
            "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
        ).status_code
        == 409
    )


def test_progress_is_recorded_without_disturbing_the_rest(client, warehouse, stations, robot):
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    run = client.post(
        "/api/runs",
        json={
            "mission_id": mission["id"],
            "robot_id": robot["id"],
            "mode": "laps",
            "laps_target": 3,
        },
    ).json()

    moved = client.patch(f"/api/runs/{run['id']}", json={"lap": 2, "step_index": 1}).json()

    assert (moved["lap"], moved["step_index"]) == (2, 1)
    assert moved["laps_target"] == 3
    assert moved["state"] == "running"


def test_a_robot_on_the_wrong_map_is_refused(client, warehouse, stations, robot):
    """
    Every station in the route names a place in the map's frame. A robot on a
    different map would accept the numbers and drive somewhere else entirely.
    """
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    client.put(f"/api/robots/{robot['id']}/map", json={"map_id": None})

    response = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    )

    assert response.status_code == 409
    assert "not on the map" in response.json()["detail"]["message"]


def test_an_empty_route_cannot_be_dispatched(client, warehouse, robot):
    mission = client.post(
        "/api/missions", json={"map_id": warehouse["id"], "name": "Empty", "steps": []}
    ).json()

    response = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    )

    assert response.status_code == 422


def test_deleting_a_route_keeps_the_record_of_what_ran(client, warehouse, stations, robot):
    """What a robot did is a record of the floor, not of the route."""
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    run = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()
    client.patch(f"/api/runs/{run['id']}", json={"state": "done"})

    client.delete(f"/api/missions/{mission['id']}")

    kept = client.get(f"/api/runs/{run['id']}").json()
    assert kept["mission_id"] is None
    assert kept["mission_name"] == "Shuttle"


def test_runs_are_listed_newest_first(client, warehouse, stations, robot):
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    first = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()
    client.patch(f"/api/runs/{first['id']}", json={"state": "done"})
    second = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()

    newest = client.get("/api/runs").json()[0]
    assert newest["id"] == second["id"]


# ── What the agent reads ──────────────────────────────────────────────────────


def test_an_idle_robot_has_no_run(client, robot):
    assert client.get(f"/api/robots/{robot['id']}/run").json() is None


def test_the_plan_inlines_the_steps(client, warehouse, stations, robot):
    """
    Resolved in one reply rather than referenced. Fetching the steps separately
    leaves a window where the route changes between the two calls, and the robot
    executes half of each.
    """
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    client.post("/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]})

    plan = client.get(f"/api/robots/{robot['id']}/run").json()

    assert plan["mission_name"] == "Shuttle"
    assert [step["station_id"] for step in plan["steps"]] == [s["id"] for s in stations]
    assert (plan["lap"], plan["step_index"], plan["state"]) == (1, 0, "running")


def test_the_plan_survives_an_agent_restart(client, warehouse, stations, robot):
    """Mid-route progress is on the server, so a restarted agent can resume."""
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    run = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()
    client.patch(f"/api/runs/{run['id']}", json={"lap": 3, "step_index": 1})

    plan = client.get(f"/api/robots/{robot['id']}/run").json()

    assert (plan["lap"], plan["step_index"]) == (3, 1)


def test_a_stopping_run_is_still_handed_over(client, warehouse, stations, robot):
    """The agent has to see `stopping` to know to finish the lap and stop."""
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    run = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()
    client.patch(f"/api/runs/{run['id']}", json={"state": "stopping"})

    assert client.get(f"/api/robots/{robot['id']}/run").json()["state"] == "stopping"


def test_a_finished_run_is_not_handed_over(client, warehouse, stations, robot):
    mission = client.post("/api/missions", json=route(warehouse, stations)).json()
    run = client.post(
        "/api/runs", json={"mission_id": mission["id"], "robot_id": robot["id"]}
    ).json()
    client.patch(f"/api/runs/{run['id']}", json={"state": "done"})

    assert client.get(f"/api/robots/{robot['id']}/run").json() is None


def test_the_plan_of_an_unknown_robot_is_404(client):
    assert client.get("/api/robots/ghost/run").status_code == 404
