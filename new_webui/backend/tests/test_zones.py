"""
Zones.

A zone is an area of a map that changes how a robot behaves inside it. Most of
these pin the rules that keep a kind and its settings consistent: a speed zone
with no limit restricts nothing, and an avoid zone with no reluctance is not an
avoid zone — both of which read as configured and do nothing.
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

SQUARE = [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]]


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


@pytest.fixture
def warehouse(client):
    return make_map(client, "Warehouse A")


def zone(warehouse, **overrides) -> dict:
    return {
        "map_id": warehouse["id"],
        "name": "Loading bay",
        "kind": "keepout",
        "polygon": SQUARE,
        **overrides,
    }


def test_registry_starts_empty(client):
    assert client.get("/api/zones").json() == []


def test_a_polygon_round_trips_as_points(client, warehouse):
    """Stored as JSON text because SQLite has no array type; it must come back."""
    body = client.post("/api/zones", json=zone(warehouse)).json()

    assert body["polygon"] == SQUARE
    assert body["kind"] == "keepout"
    assert body["enabled"] is True


def test_a_zone_cannot_exist_without_its_map(client):
    response = client.post("/api/zones", json=zone({"id": "nope"}))
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("kind", "extra"),
    [
        ("keepout", {}),
        ("avoid", {"avoid_cost": 60}),
        ("speed", {"speed_limit": 0.3}),
        ("binary", {}),
    ],
)
def test_every_filter_nav2_offers_is_accepted(client, warehouse, kind, extra):
    """keepout and avoid share a Nav2 filter; speed and binary have their own."""
    response = client.post("/api/zones", json=zone(warehouse, kind=kind, **extra))
    assert response.status_code == 201


def test_an_unknown_kind_is_refused(client, warehouse):
    assert client.post("/api/zones", json=zone(warehouse, kind="one_way")).status_code == 422


# ── A kind and its settings have to agree ─────────────────────────────────────


def test_a_speed_zone_without_a_limit_is_refused(client, warehouse):
    """It would read as configured and restrict nothing."""
    response = client.post("/api/zones", json=zone(warehouse, kind="speed"))
    assert response.status_code == 422


def test_a_limit_on_a_keepout_zone_is_refused(client, warehouse):
    """A speed limit on an area nobody may enter is a number nobody reads."""
    response = client.post("/api/zones", json=zone(warehouse, kind="keepout", speed_limit=0.5))
    assert response.status_code == 422


def test_an_avoid_zone_without_a_cost_is_refused(client, warehouse):
    assert client.post("/api/zones", json=zone(warehouse, kind="avoid")).status_code == 422


@pytest.mark.parametrize("cost", [0, 100])
def test_an_avoid_cost_outside_the_middle_is_refused(client, warehouse, cost):
    """100 is a keepout and 0 is no reluctance at all; neither is an avoid zone."""
    response = client.post("/api/zones", json=zone(warehouse, kind="avoid", avoid_cost=cost))
    assert response.status_code == 422


def test_a_zero_speed_limit_is_refused(client, warehouse):
    """Zero is a keepout expressed as a speed, and Nav2 reads 0 as no limit."""
    response = client.post("/api/zones", json=zone(warehouse, kind="speed", speed_limit=0))
    assert response.status_code == 422


# ── Polygons ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("points", [[], [[0.0, 0.0]], [[0.0, 0.0], [1.0, 1.0]]])
def test_fewer_than_three_points_is_refused(client, warehouse, points):
    """Two points make a line, and a line encloses nothing."""
    assert client.post("/api/zones", json=zone(warehouse, polygon=points)).status_code == 422


def test_a_non_finite_coordinate_is_refused(client, warehouse):
    """NaN survives JSON and then produces a mask with no zone in it, silently."""
    body = (
        f'{{"map_id": "{warehouse["id"]}", "name": "Bad", "kind": "keepout", '
        '"polygon": [[0.0, 0.0], [NaN, 0.0], [1.0, 1.0]]}'
    )
    response = client.post(
        "/api/zones", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


def test_too_many_points_are_refused(client, warehouse):
    huge = [[float(i), 0.0] for i in range(501)]
    assert client.post("/api/zones", json=zone(warehouse, polygon=huge)).status_code == 422


# ── Listing and editing ───────────────────────────────────────────────────────


def test_listing_can_be_scoped_to_a_map_and_a_kind(client, warehouse):
    other = make_map(client, "Loading Bay", fill=FREE)
    client.post("/api/zones", json=zone(warehouse, name="A", kind="keepout"))
    client.post("/api/zones", json=zone(warehouse, name="B", kind="speed", speed_limit=0.4))
    client.post("/api/zones", json=zone(other, name="C", kind="keepout"))

    assert len(client.get("/api/zones", params={"map_id": warehouse["id"]}).json()) == 2
    scoped = client.get(
        "/api/zones", params={"map_id": warehouse["id"], "kind": "speed"}
    ).json()
    assert [row["name"] for row in scoped] == ["B"]


def test_names_are_unique_per_map_not_globally(client, warehouse):
    other = make_map(client, "Loading Bay", fill=FREE)
    assert client.post("/api/zones", json=zone(warehouse)).status_code == 201
    assert client.post("/api/zones", json=zone(other)).status_code == 201
    response = client.post("/api/zones", json=zone(warehouse))
    assert response.status_code == 409
    assert response.json()["detail"]["field"] == "name"


def test_reshaping_sends_the_polygon_alone(client, warehouse):
    """The case a partial update exists for."""
    created = client.post("/api/zones", json=zone(warehouse, note="by the shutter")).json()
    reshaped = [[0.0, 0.0], [3.0, 0.0], [3.0, 3.0], [0.0, 3.0], [-1.0, 1.5]]

    updated = client.patch(f"/api/zones/{created['id']}", json={"polygon": reshaped}).json()

    assert updated["polygon"] == reshaped
    assert updated["name"] == "Loading bay"
    assert updated["note"] == "by the shutter"


def test_a_zone_can_be_switched_off_without_being_deleted(client, warehouse):
    """A zone up for a fortnight of building work should come back the same shape."""
    created = client.post("/api/zones", json=zone(warehouse)).json()

    disabled = client.patch(f"/api/zones/{created['id']}", json={"enabled": False}).json()

    assert disabled["enabled"] is False
    assert disabled["polygon"] == SQUARE


def test_changing_kind_clears_the_setting_the_old_kind_needed(client, warehouse):
    """
    The operator asked for a different kind of zone. Making them delete the old
    number by hand first is a step with only one possible answer.
    """
    created = client.post(
        "/api/zones", json=zone(warehouse, kind="speed", speed_limit=0.3)
    ).json()

    changed = client.patch(f"/api/zones/{created['id']}", json={"kind": "keepout"}).json()

    assert changed["kind"] == "keepout"
    assert changed["speed_limit"] is None


def test_changing_kind_to_one_that_needs_a_setting_requires_it(client, warehouse):
    created = client.post("/api/zones", json=zone(warehouse, kind="keepout")).json()

    response = client.patch(f"/api/zones/{created['id']}", json={"kind": "speed"})

    assert response.status_code == 422
    assert "speed_limit is required" in response.json()["detail"]


def test_changing_kind_and_its_setting_together_works(client, warehouse):
    created = client.post("/api/zones", json=zone(warehouse, kind="keepout")).json()

    changed = client.patch(
        f"/api/zones/{created['id']}", json={"kind": "avoid", "avoid_cost": 40}
    ).json()

    assert (changed["kind"], changed["avoid_cost"]) == ("avoid", 40)


def test_unknown_fields_are_refused_rather_than_ignored(client, warehouse):
    created = client.post("/api/zones", json=zone(warehouse)).json()
    assert client.patch(f"/api/zones/{created['id']}", json={"colour": "red"}).status_code == 422


# ── Deletion ──────────────────────────────────────────────────────────────────


def test_delete_removes_only_that_zone(client, warehouse):
    first = client.post("/api/zones", json=zone(warehouse, name="A")).json()
    client.post("/api/zones", json=zone(warehouse, name="B"))

    assert client.delete(f"/api/zones/{first['id']}").status_code == 204
    assert [row["name"] for row in client.get("/api/zones").json()] == ["B"]


def test_deleting_a_map_takes_its_zones_with_it(client, warehouse):
    """A polygon outliving its map is a list of coordinates with no frame."""
    client.post("/api/zones", json=zone(warehouse))

    assert client.delete(f"/api/maps/{warehouse['id']}").status_code == 204
    assert client.get("/api/zones").json() == []


def test_deleting_an_unknown_zone_is_404(client):
    assert client.delete("/api/zones/nope").status_code == 404


# ── Explicit null on a NOT NULL field (F-09) ──────────────────────────────────


def test_enabled_null_is_refused_not_read_as_off(client, warehouse):
    """`enabled: null` used to be stored as 0 and switch a keep-out zone off."""
    created = client.post("/api/zones", json=zone(warehouse)).json()

    response = client.patch(f"/api/zones/{created['id']}", json={"enabled": None})

    assert response.status_code == 422
    assert "enabled cannot be null" in response.text
    assert client.get(f"/api/zones/{created['id']}").json()["enabled"] is True


@pytest.mark.parametrize("field", ["name", "kind", "polygon"])
def test_null_on_a_required_field_is_422(client, warehouse, field):
    created = client.post("/api/zones", json=zone(warehouse)).json()

    response = client.patch(f"/api/zones/{created['id']}", json={field: None})

    assert response.status_code == 422
    assert f"{field} cannot be null" in response.text


def test_nullable_zone_fields_still_clear_with_null(client, warehouse):
    created = client.post(
        "/api/zones", json=zone(warehouse, kind="speed", speed_limit=0.3, note="slow")
    ).json()

    response = client.patch(
        f"/api/zones/{created['id']}",
        json={"kind": "keepout", "speed_limit": None, "note": None},
    )

    assert response.status_code == 200
    assert (response.json()["speed_limit"], response.json()["note"]) == (None, None)
