"""
Robot registry endpoints.

Several of these pin behaviour that the previous API got wrong, and the test
names say which defect they guard.
"""

from __future__ import annotations

import pytest


def test_registry_starts_empty(client):
    response = client.get("/api/robots")
    assert response.status_code == 200
    assert response.json() == []


def test_create_returns_201_and_assigns_id_and_accent(client, robot_payload):
    response = client.post("/api/robots", json=robot_payload)
    assert response.status_code == 201

    body = response.json()
    assert body["name"] == "AMR-01"
    assert body["bridge_url"] == "ws://192.168.1.50:8765"
    assert body["id"], "server assigns the id"
    assert body["accent"] == 1
    assert body["ros_domain_id"] is None


def test_accents_are_handed_out_lowest_first(client):
    for index in range(3):
        client.post(
            "/api/robots",
            json={"name": f"AMR-{index}", "bridge_url": f"ws://10.0.0.{index}:8765"},
        )
    accents = [robot["accent"] for robot in client.get("/api/robots").json()]
    assert sorted(accents) == [1, 2, 3]


def test_deleting_a_robot_frees_its_accent(client):
    first = client.post("/api/robots", json={"name": "A", "bridge_url": "ws://10.0.0.1:8765"}).json()
    client.post("/api/robots", json={"name": "B", "bridge_url": "ws://10.0.0.2:8765"})

    client.delete(f"/api/robots/{first['id']}")
    third = client.post("/api/robots", json={"name": "C", "bridge_url": "ws://10.0.0.3:8765"}).json()
    assert third["accent"] == 1, "the freed colour is reused"


def test_duplicate_name_is_a_conflict_not_a_bad_request(client, robot_payload):
    client.post("/api/robots", json=robot_payload)
    response = client.post(
        "/api/robots",
        json={"name": "amr-01", "bridge_url": "ws://10.0.0.9:8765"},
    )
    # Two robots sharing a name is how an operator drives the wrong one.
    # Case-insensitive, because "AMR-01" and "amr-01" are one machine to a human.
    assert response.status_code == 409
    assert response.json()["detail"]["field"] == "name"


def test_duplicate_bridge_is_a_conflict(client, robot_payload):
    client.post("/api/robots", json=robot_payload)
    response = client.post(
        "/api/robots",
        json={"name": "AMR-02", "bridge_url": robot_payload["bridge_url"]},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["field"] == "bridge_url"


def test_rejects_a_non_websocket_bridge(client):
    response = client.post(
        "/api/robots",
        json={"name": "AMR-01", "bridge_url": "http://192.168.1.50:8765"},
    )
    assert response.status_code == 422


def test_rejects_unknown_fields_instead_of_dropping_them(client):
    """
    The defect that cost the old API real data: Pydantic ignores unknown keys
    by default, so missions lost station_id and docks lost their whole approach
    pose, silently, on every write.
    """
    response = client.post(
        "/api/robots",
        json={"name": "AMR-01", "bridge_url": "ws://10.0.0.1:8765", "colour": "red"},
    )
    assert response.status_code == 422


def test_ros_domain_zero_is_stored_as_zero_not_null(client):
    """Zero is a valid ROS domain; only an absent value means 'not set'."""
    body = client.post(
        "/api/robots",
        json={"name": "AMR-01", "bridge_url": "ws://10.0.0.1:8765", "ros_domain_id": 0},
    ).json()
    assert body["ros_domain_id"] == 0


def test_ros_domain_out_of_range_is_rejected(client):
    for domain in (-1, 233):
        response = client.post(
            "/api/robots",
            json={"name": f"R{domain}", "bridge_url": f"ws://10.0.0.{abs(domain)}:8765",
                  "ros_domain_id": domain},
        )
        assert response.status_code == 422


def test_patch_leaves_omitted_fields_alone(client):
    """
    The distinction the old PUT-based API could not express. Omitting a field
    there reset it to its default — which is how changing a destination's type
    wiped its orientation.
    """
    created = client.post(
        "/api/robots",
        json={"name": "AMR-01", "bridge_url": "ws://10.0.0.1:8765", "ros_domain_id": 42},
    ).json()

    updated = client.patch(f"/api/robots/{created['id']}", json={"name": "AMR-09"}).json()
    assert updated["name"] == "AMR-09"
    assert updated["ros_domain_id"] == 42, "an omitted field must survive"
    assert updated["bridge_url"] == created["bridge_url"]


def test_patch_with_explicit_null_clears_the_field(client):
    created = client.post(
        "/api/robots",
        json={"name": "AMR-01", "bridge_url": "ws://10.0.0.1:8765", "ros_domain_id": 42},
    ).json()

    updated = client.patch(f"/api/robots/{created['id']}", json={"ros_domain_id": None}).json()
    assert updated["ros_domain_id"] is None


def test_patch_touches_updated_at(client, robot_payload):
    created = client.post("/api/robots", json=robot_payload).json()
    updated = client.patch(f"/api/robots/{created['id']}", json={"serial": "SN-1"}).json()
    assert updated["created_at"] == created["created_at"]
    assert updated["updated_at"] >= created["updated_at"]


def test_patch_to_a_name_another_robot_holds_is_a_conflict(client):
    client.post("/api/robots", json={"name": "AMR-01", "bridge_url": "ws://10.0.0.1:8765"})
    second = client.post(
        "/api/robots", json={"name": "AMR-02", "bridge_url": "ws://10.0.0.2:8765"}
    ).json()

    response = client.patch(f"/api/robots/{second['id']}", json={"name": "AMR-01"})
    assert response.status_code == 409


def test_patch_to_its_own_name_is_allowed(client, robot_payload):
    created = client.post("/api/robots", json=robot_payload).json()
    response = client.patch(f"/api/robots/{created['id']}", json={"name": created["name"]})
    assert response.status_code == 200


def test_missing_robot_is_404_on_every_verb(client):
    assert client.get("/api/robots/nope").status_code == 404
    assert client.patch("/api/robots/nope", json={"name": "X"}).status_code == 404
    assert client.delete("/api/robots/nope").status_code == 404


def test_delete_returns_204_and_removes_the_record(client, robot_payload):
    created = client.post("/api/robots", json=robot_payload).json()
    assert client.delete(f"/api/robots/{created['id']}").status_code == 204
    assert client.get("/api/robots").json() == []


def test_list_is_ordered_by_name_case_insensitively(client):
    for name, host in [("zebra", "1"), ("Alpha", "2"), ("mid", "3")]:
        client.post("/api/robots", json={"name": name, "bridge_url": f"ws://10.0.0.{host}:8765"})
    names = [robot["name"] for robot in client.get("/api/robots").json()]
    assert names == ["Alpha", "mid", "zebra"]


def test_blank_name_is_rejected(client):
    response = client.post("/api/robots", json={"name": "   ", "bridge_url": "ws://10.0.0.1:8765"})
    assert response.status_code == 422


def test_name_and_namespace_are_trimmed(client):
    body = client.post(
        "/api/robots",
        json={"name": "  AMR-01  ", "bridge_url": "ws://10.0.0.1:8765", "namespace": "/amr_01/"},
    ).json()
    assert body["name"] == "AMR-01"
    assert body["namespace"] == "amr_01"


# ── Desired mode ──────────────────────────────────────────────────────────────
#
# What a robot is *supposed* to be doing, as opposed to what it is doing. Before
# this the mode lived only in the agent's memory, so an agent that restarted
# came back idle and nothing reported it — and a robot needed somebody to press
# a button before it would work at all.


def test_a_new_robot_defaults_to_navigating(client, robot_payload):
    """
    A robot that is powered on should be ready for work.

    Nav2 running is not the robot moving: an idle planner plans nothing, and the
    robot only moves when a mission gives it a goal.
    """
    body = client.post("/api/robots", json=robot_payload).json()
    assert body["desired_mode"] == "nav"


@pytest.mark.parametrize("mode", ["nav", "idle", "map"])
def test_every_mode_can_be_asked_for(client, robot_payload, mode):
    created = client.post("/api/robots", json=robot_payload).json()

    updated = client.put(f"/api/robots/{created['id']}/mode", json={"desired_mode": mode}).json()

    assert updated["desired_mode"] == mode
    assert client.get(f"/api/robots/{created['id']}").json()["desired_mode"] == mode


def test_an_unknown_mode_is_refused(client, robot_payload):
    created = client.post("/api/robots", json=robot_payload).json()
    response = client.put(f"/api/robots/{created['id']}/mode", json={"desired_mode": "fly"})
    assert response.status_code == 422


def test_asking_for_nav_without_a_map_is_still_accepted(client, robot_payload):
    """
    The agent stays idle and says why. Refusing here would mean an operator has
    to remember to come back and set it after assigning the map.
    """
    created = client.post("/api/robots", json=robot_payload).json()
    assert created["active_map_id"] is None

    response = client.put(f"/api/robots/{created['id']}/mode", json={"desired_mode": "nav"})

    assert response.status_code == 200


def test_setting_the_mode_leaves_the_rest_of_the_record_alone(client, robot_payload):
    created = client.post("/api/robots", json=robot_payload).json()

    updated = client.put(f"/api/robots/{created['id']}/mode", json={"desired_mode": "idle"}).json()

    assert updated["name"] == created["name"]
    assert updated["bridge_url"] == created["bridge_url"]


def test_the_mode_of_an_unknown_robot_is_404(client):
    assert client.put("/api/robots/ghost/mode", json={"desired_mode": "nav"}).status_code == 404


def test_unknown_fields_are_refused_rather_than_ignored(client, robot_payload):
    created = client.post("/api/robots", json=robot_payload).json()
    response = client.put(
        f"/api/robots/{created['id']}/mode", json={"desired_mode": "nav", "force": True}
    )
    assert response.status_code == 422
