"""
Station registry.

A station is a named pose in one map's frame. The rules that matter: it cannot
exist without its map, its coordinates are metres in that frame and never
pixels, and a partial update must not wipe the fields it does not mention —
dragging a marker sends x and y alone.
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

OCCUPIED, UNKNOWN, FREE = 0, 205, 254


def pgm(width: int = 12, height: int = 7, fill: int = OCCUPIED) -> bytes:
    return f"P5\n{width} {height}\n255\n".encode() + bytes([fill]) * (width * height)


@pytest.fixture
def stored_map(client):
    return client.post(
        "/api/maps",
        data={"name": "Warehouse A"},
        files={
            "yaml_file": ("map.yaml", MAP_YAML, "application/x-yaml"),
            "image_file": ("warehouse.pgm", pgm(), "image/x-portable-graymap"),
        },
    ).json()


@pytest.fixture
def robot(client):
    return client.post(
        "/api/robots", json={"name": "AMR-01", "bridge_url": "ws://10.0.0.1:8765"}
    ).json()


def station(stored_map, **overrides) -> dict:
    return {
        "map_id": stored_map["id"],
        "name": "Dock 1",
        "type": "charging",
        "x": 3.25,
        "y": -1.5,
        "yaw": 1.5708,
        **overrides,
    }


def test_registry_starts_empty(client):
    assert client.get("/api/stations").json() == []


def test_create_returns_the_pose_as_given(client, stored_map):
    body = client.post("/api/stations", json=station(stored_map)).json()

    assert (body["x"], body["y"]) == (3.25, -1.5)
    assert body["yaw"] == pytest.approx(1.5708)
    assert body["type"] == "charging"
    assert body["map_id"] == stored_map["id"]


def test_station_cannot_exist_without_its_map(client):
    """A pose with no frame is not a location."""
    response = client.post("/api/stations", json=station({"id": "nope"}))

    assert response.status_code == 404
    assert "Map not found" in response.json()["detail"]


def test_names_are_unique_per_map_not_globally(client, stored_map):
    """
    Two sites may both have a "Dock 1". A mission names a station within one
    map, so only that pairing has to be unambiguous.
    """
    other = client.post(
        "/api/maps",
        data={"name": "Loading Bay"},
        files={
            "yaml_file": ("map.yaml", MAP_YAML, "application/x-yaml"),
            "image_file": ("warehouse.pgm", pgm(fill=FREE), "image/x-portable-graymap"),
        },
    ).json()

    assert client.post("/api/stations", json=station(stored_map)).status_code == 201
    assert client.post("/api/stations", json=station(other)).status_code == 201


def test_a_duplicate_name_on_one_map_is_refused(client, stored_map):
    client.post("/api/stations", json=station(stored_map))

    response = client.post("/api/stations", json=station(stored_map))

    assert response.status_code == 409
    # The form has to be able to point at the offending input.
    assert response.json()["detail"]["field"] == "name"


def test_duplicate_detection_ignores_case(client, stored_map):
    client.post("/api/stations", json=station(stored_map, name="Dock 1"))
    assert client.post("/api/stations", json=station(stored_map, name="dock 1")).status_code == 409


def test_listing_can_be_scoped_to_one_map(client, stored_map):
    other = client.post(
        "/api/maps",
        data={"name": "Loading Bay"},
        files={
            "yaml_file": ("map.yaml", MAP_YAML, "application/x-yaml"),
            "image_file": ("warehouse.pgm", pgm(fill=FREE), "image/x-portable-graymap"),
        },
    ).json()
    client.post("/api/stations", json=station(stored_map, name="A"))
    client.post("/api/stations", json=station(other, name="B"))

    scoped = client.get("/api/stations", params={"map_id": stored_map["id"]}).json()

    assert [row["name"] for row in scoped] == ["A"]
    assert len(client.get("/api/stations").json()) == 2


def test_an_unknown_type_is_refused(client, stored_map):
    """The four the robot understands, and nothing else."""
    response = client.post("/api/stations", json=station(stored_map, type="parking"))
    assert response.status_code == 422


@pytest.mark.parametrize("kind", ["pick", "drop", "pick_drop", "charging"])
def test_every_type_the_robot_understands_is_accepted(client, stored_map, kind):
    assert client.post("/api/stations", json=station(stored_map, type=kind)).status_code == 201


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_a_non_finite_coordinate_is_refused(client, stored_map, literal):
    """
    Python's JSON reader accepts these, so they arrive as real floats and then
    poison every distance calculation downstream without raising anything.
    Written as a raw body because a JSON *writer* refuses to emit them.
    """
    body = (
        f'{{"map_id": "{stored_map["id"]}", "name": "Dock 1", "type": "pick", '
        f'"x": {literal}, "y": 0.0, "yaw": 0.0}}'
    )

    response = client.post(
        "/api/stations", content=body, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422


def test_teaching_records_which_robot_was_standing_there(client, stored_map, robot):
    body = client.post(
        "/api/stations", json=station(stored_map, taught_by_robot_id=robot["id"])
    ).json()

    assert body["taught_by_robot_id"] == robot["id"]


def test_teaching_by_an_unknown_robot_is_refused(client, stored_map):
    response = client.post("/api/stations", json=station(stored_map, taught_by_robot_id="ghost"))
    assert response.status_code == 404


# ── Partial update ────────────────────────────────────────────────────────────


def test_moving_a_marker_sends_coordinates_alone(client, stored_map):
    """
    The case this exists for. A drag patches x and y; the name, type and note
    must survive untouched.
    """
    created = client.post(
        "/api/stations", json=station(stored_map, note="by the shutter")
    ).json()

    moved = client.patch(f"/api/stations/{created['id']}", json={"x": 9.0, "y": 4.5}).json()

    assert (moved["x"], moved["y"]) == (9.0, 4.5)
    assert moved["name"] == "Dock 1"
    assert moved["type"] == "charging"
    assert moved["note"] == "by the shutter"
    assert moved["yaw"] == pytest.approx(1.5708)


def test_an_empty_patch_changes_nothing(client, stored_map):
    created = client.post("/api/stations", json=station(stored_map)).json()

    unchanged = client.patch(f"/api/stations/{created['id']}", json={}).json()

    assert unchanged["name"] == created["name"]
    assert unchanged["x"] == created["x"]


def test_a_note_can_be_cleared_by_sending_null(client, stored_map):
    """Omitted keeps, null clears. Both have to be expressible."""
    created = client.post("/api/stations", json=station(stored_map, note="temporary")).json()

    cleared = client.patch(f"/api/stations/{created['id']}", json={"note": None}).json()

    assert cleared["note"] is None


def test_renaming_onto_a_sibling_is_refused(client, stored_map):
    client.post("/api/stations", json=station(stored_map, name="Dock 1"))
    second = client.post("/api/stations", json=station(stored_map, name="Dock 2")).json()

    response = client.patch(f"/api/stations/{second['id']}", json={"name": "Dock 1"})

    assert response.status_code == 409
    assert client.get(f"/api/stations/{second['id']}").json()["name"] == "Dock 2"


def test_patching_an_unknown_station_is_404(client):
    assert client.patch("/api/stations/nope", json={"x": 1.0}).status_code == 404


def test_unknown_fields_are_refused_rather_than_ignored(client, stored_map):
    """
    The previous contract dropped what it had not declared, so a client sending
    the wrong key got a silent no-op.
    """
    created = client.post("/api/stations", json=station(stored_map)).json()
    assert client.patch(f"/api/stations/{created['id']}", json={"xx": 1.0}).status_code == 422


# ── Deletion and the map it belongs to ────────────────────────────────────────


def test_delete_removes_only_that_station(client, stored_map):
    first = client.post("/api/stations", json=station(stored_map, name="A")).json()
    client.post("/api/stations", json=station(stored_map, name="B"))

    assert client.delete(f"/api/stations/{first['id']}").status_code == 204
    assert [row["name"] for row in client.get("/api/stations").json()] == ["B"]


def test_deleting_an_unknown_station_is_404(client):
    assert client.delete("/api/stations/nope").status_code == 404


def test_deleting_a_map_takes_its_stations_with_it(client, stored_map):
    """
    A station outliving its map would be a coordinate with no frame. Map deletion
    already refuses while a robot is assigned, so this cannot fire on a map
    anything is running.
    """
    client.post("/api/stations", json=station(stored_map))

    assert client.delete(f"/api/maps/{stored_map['id']}").status_code == 204
    assert client.get("/api/stations").json() == []


def test_a_map_reports_how_many_stations_go_with_it(client, stored_map):
    """So the delete confirmation can say what else is at stake."""
    client.post("/api/stations", json=station(stored_map, name="A"))
    client.post("/api/stations", json=station(stored_map, name="B"))

    body = client.get(f"/api/maps/{stored_map['id']}/stations/count").json()

    assert body["stations"] == 2


def test_station_count_of_an_unknown_map_is_404(client):
    assert client.get("/api/maps/nope/stations/count").status_code == 404
