"""
Map registry.

Several of these pin rules that only exist because the old design broke them:
maps were overwritten in place, a read could delete them, and the yaml/image
pair could come apart.
"""

from __future__ import annotations

import hashlib

import pytest
import yaml as pyyaml

MAP_YAML = b"""image: warehouse.pgm
resolution: 0.05
origin: [-1.5, -2.5, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
"""


# The three values a ROS occupancy map may hold. Uploads are rejected for
# anything else, so a fixture that wants a *different* image has to pick a
# different one of these rather than an arbitrary byte.
OCCUPIED, UNKNOWN, FREE = 0, 205, 254


def pgm(width: int = 12, height: int = 7, fill: int = OCCUPIED) -> bytes:
    return f"P5\n{width} {height}\n255\n".encode() + bytes([fill]) * (width * height)


def mixed_pgm(width: int = 12, height: int = 7, *, stripe: int = FREE) -> bytes:
    """A canonical image whose hash differs from any flat fill."""
    body = bytearray(bytes([OCCUPIED]) * (width * height))
    body[: width] = bytes([stripe]) * width
    return f"P5\n{width} {height}\n255\n".encode() + bytes(body)


def upload(client, name="Warehouse A", yaml_bytes=MAP_YAML, image=None, **form):
    return client.post(
        "/api/maps",
        data={"name": name, **form},
        files={
            "yaml_file": ("map.yaml", yaml_bytes, "application/x-yaml"),
            "image_file": (
                "warehouse.pgm",
                image if image is not None else pgm(),
                "image/x-portable-graymap",
            ),
        },
    )


@pytest.fixture
def robot(client):
    return client.post(
        "/api/robots", json={"name": "AMR-01", "bridge_url": "ws://10.0.0.1:8765"}
    ).json()


def test_registry_starts_empty(client):
    assert client.get("/api/maps").json() == []


def test_response_names_the_stored_files(client):
    """
    A client caching the pair has to store the image under the name the stored
    yaml refers to, so those names are part of the contract.
    """
    body = upload(client).json()
    assert body["yaml_file"] == "map.yaml"
    assert body["image_file"] == "map.pgm"


def test_upload_returns_201_with_parsed_metadata(client):
    response = upload(client)
    assert response.status_code == 201

    body = response.json()
    assert body["name"] == "Warehouse A"
    assert body["version"] == 1
    assert body["resolution"] == 0.05
    assert body["origin_x"] == -1.5
    assert body["origin_y"] == -2.5
    assert body["occupied_thresh"] == 0.65
    # Read from the PGM header, so the UI can show extent without the image.
    assert (body["width"], body["height"]) == (12, 7)
    assert body["content_hash"] == hashlib.sha256(pgm()).hexdigest()


def test_saving_the_same_name_creates_a_new_version(client):
    """
    Maps are never overwritten.

    Stations store coordinates in a specific map frame, so replacing a map's
    contents silently invalidates every station attached to it — on every robot
    still running the old one.
    """
    first = upload(client, image=pgm(fill=0)).json()
    second = upload(client, image=pgm(fill=FREE)).json()

    assert first["version"] == 1
    assert second["version"] == 2
    assert first["id"] != second["id"]
    assert len(client.get("/api/maps").json()) == 2


def test_reuploading_identical_content_returns_the_existing_version(client):
    """An agent retrying after a dropped connection must not leave duplicates."""
    first = upload(client).json()
    again = upload(client)
    assert again.status_code == 201
    assert again.json()["id"] == first["id"]
    assert again.json()["version"] == 1
    assert len(client.get("/api/maps").json()) == 1


def test_different_names_version_independently(client):
    assert upload(client, name="Warehouse A").json()["version"] == 1
    assert upload(client, name="Warehouse B").json()["version"] == 1


def test_the_stored_yaml_points_at_the_stored_image(client):
    """
    The pair must stay a pair.

    A map saved as warehouse.pgm but stored as map.pgm yields a yaml that
    map_server cannot resolve — on a robot, at the moment it is asked to
    navigate.
    """
    created = upload(client).json()
    stored = client.get(f"/api/maps/{created['id']}/files/yaml")
    assert stored.status_code == 200

    document = pyyaml.safe_load(stored.content)
    assert document["image"] == "map.pgm"
    # The rest of the document survives the rewrite.
    assert document["resolution"] == 0.05
    assert document["origin"] == [-1.5, -2.5, 0.0]


def test_image_download_carries_the_content_hash(client):
    created = upload(client).json()
    response = client.get(f"/api/maps/{created['id']}/files/image")
    assert response.status_code == 200
    # The robot compares this against its cache to decide whether to download.
    assert response.headers["x-content-hash"] == created["content_hash"]
    # Replacing keeps the map id and URL, so clients must not reuse old bytes.
    assert response.headers["cache-control"] == "no-store, must-revalidate"
    assert response.headers["pragma"] == "no-cache"
    assert response.content == pgm()


def test_rejects_yaml_without_an_image_field(client):
    response = upload(client, yaml_bytes=b"resolution: 0.05\n")
    assert response.status_code == 422
    assert "image" in response.json()["detail"]


def test_rejects_unparseable_yaml(client):
    response = upload(client, yaml_bytes=b"image: [unclosed\n")
    assert response.status_code == 422


def test_rejects_a_non_map_image_type(client):
    response = client.post(
        "/api/maps",
        data={"name": "Warehouse A"},
        files={
            "yaml_file": ("map.yaml", MAP_YAML, "application/x-yaml"),
            "image_file": ("map.jpg", b"\xff\xd8\xff", "image/jpeg"),
        },
    )
    assert response.status_code == 422


def test_rejects_a_blank_or_unsafe_name(client):
    assert upload(client, name="   ").status_code == 422
    # Sanitising silently would produce a second map nobody meant to create.
    assert upload(client, name="../../etc/passwd").status_code == 422


def test_rejects_an_unknown_creating_robot(client):
    assert upload(client, robot_id="nope").status_code == 404


def test_records_which_robot_surveyed_it(client, robot):
    body = upload(client, robot_id=robot["id"], note="first survey").json()
    assert body["created_by_robot_id"] == robot["id"]
    assert body["note"] == "first survey"


def test_deleting_the_surveying_robot_keeps_the_map(client, robot):
    """Retiring a robot must not delete the maps it produced."""
    created = upload(client, robot_id=robot["id"]).json()
    client.delete(f"/api/robots/{robot['id']}")
    assert client.get(f"/api/maps/{created['id']}").json()["created_by_robot_id"] is None


def test_assign_map_to_robot(client, robot):
    created = upload(client).json()
    response = client.put(f"/api/robots/{robot['id']}/map", json={"map_id": created["id"]})
    assert response.status_code == 200
    assert response.json()["active_map_id"] == created["id"]


def test_assignment_can_be_cleared(client, robot):
    created = upload(client).json()
    client.put(f"/api/robots/{robot['id']}/map", json={"map_id": created["id"]})
    assert client.put(f"/api/robots/{robot['id']}/map", json={"map_id": None}).json()[
        "active_map_id"
    ] is None


def test_assigning_an_unknown_map_is_404(client, robot):
    assert client.put(f"/api/robots/{robot['id']}/map", json={"map_id": "nope"}).status_code == 404


def test_delete_is_refused_while_a_robot_is_assigned(client, robot):
    """
    A read can never delete a map here, and neither can a careless write.

    The old backend's GET /api/maps deleted rows whose file had gone, and the
    cascade took every keepout zone, dock and destination with them.
    """
    created = upload(client).json()
    client.put(f"/api/robots/{robot['id']}/map", json={"map_id": created["id"]})

    response = client.delete(f"/api/maps/{created['id']}")
    assert response.status_code == 409
    assert response.json()["detail"]["robots"] == ["AMR-01"]
    assert client.get(f"/api/maps/{created['id']}").status_code == 200


def test_delete_succeeds_once_the_robot_is_moved_off(client, robot):
    created = upload(client).json()
    client.put(f"/api/robots/{robot['id']}/map", json={"map_id": created["id"]})
    client.put(f"/api/robots/{robot['id']}/map", json={"map_id": None})

    assert client.delete(f"/api/maps/{created['id']}").status_code == 204
    assert client.get(f"/api/maps/{created['id']}").status_code == 404


def test_delete_removes_the_files_too(client, settings):
    created = upload(client).json()
    directory = settings.maps_dir / created["id"]
    assert directory.is_dir()

    client.delete(f"/api/maps/{created['id']}")
    assert not directory.exists()


def test_listing_a_read_does_not_mutate(client):
    """Reading the registry twice must leave it exactly as it was."""
    upload(client, name="Warehouse A")
    upload(client, name="Warehouse B")
    before = client.get("/api/maps").json()
    client.get("/api/maps")
    assert client.get("/api/maps").json() == before


def test_missing_map_and_bad_file_selector_are_404(client):
    assert client.get("/api/maps/nope").status_code == 404
    assert client.get("/api/maps/nope/files/yaml").status_code == 404
    created = upload(client).json()
    assert client.get(f"/api/maps/{created['id']}/files/sideways").status_code == 404


def test_registered_map_with_missing_files_reports_gone(client, settings):
    """
    A row whose files vanished is a distinct failure from a map that never
    existed, and saying so is what makes it fixable.
    """
    created = upload(client).json()
    for path in (settings.maps_dir / created["id"]).iterdir():
        path.unlink()
    assert client.get(f"/api/maps/{created['id']}/files/yaml").status_code == 410


def test_list_is_ordered_by_name_then_newest_version(client):
    upload(client, name="Beta", image=pgm(fill=UNKNOWN))
    upload(client, name="Alpha", image=pgm(fill=UNKNOWN))
    upload(client, name="Alpha", image=pgm(fill=FREE))

    rows = client.get("/api/maps").json()
    assert [(r["name"], r["version"]) for r in rows] == [("Alpha", 2), ("Alpha", 1), ("Beta", 1)]


# ── Rename ────────────────────────────────────────────────────────────────────


def test_rename_moves_every_version_of_the_lineage(client):
    """
    The name IS the lineage key, so a rename that moved one row would leave the
    others behind and start the new name at whatever version that row held.
    """
    v1 = upload(client).json()
    v2 = upload(client, image=pgm(fill=FREE)).json()
    assert (v1["version"], v2["version"]) == (1, 2)

    renamed = client.patch(f"/api/maps/{v2['id']}", json={"name": "Warehouse B"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Warehouse B"

    names = {row["version"]: row["name"] for row in client.get("/api/maps").json()}
    assert names == {1: "Warehouse B", 2: "Warehouse B"}


def test_rename_keeps_ids_hashes_and_versions(client):
    """A rename is metadata only: nothing on disk moves, nothing is re-versioned."""
    before = upload(client).json()

    after = client.patch(f"/api/maps/{before['id']}", json={"name": "Renamed"}).json()

    assert after["id"] == before["id"]
    assert after["content_hash"] == before["content_hash"]
    assert after["version"] == before["version"]
    assert after["image_file"] == before["image_file"]


def test_rename_does_not_detach_an_assigned_robot(client, robot):
    """Robots reference a map by id, so the assignment has to survive a rename."""
    stored = upload(client).json()
    client.put(f"/api/robots/{robot['id']}/map", json={"map_id": stored["id"]})

    client.patch(f"/api/maps/{stored['id']}", json={"name": "Warehouse B"})

    assert client.get(f"/api/robots/{robot['id']}").json()["active_map_id"] == stored["id"]


def test_rename_onto_an_existing_name_is_refused(client):
    """
    Merging two lineages is not a rename — the version numbers collide — so this
    refuses rather than silently renumbering somebody's map.
    """
    upload(client, name="Warehouse A")
    other = upload(client, name="Loading Bay", image=pgm(fill=FREE)).json()

    response = client.patch(f"/api/maps/{other['id']}", json={"name": "Warehouse A"})

    assert response.status_code == 409
    assert client.get(f"/api/maps/{other['id']}").json()["name"] == "Loading Bay"


def test_rename_can_change_only_the_case(client):
    """Fixing capitalisation is a rename onto itself, not a collision."""
    stored = upload(client, name="warehouse a").json()

    response = client.patch(f"/api/maps/{stored['id']}", json={"name": "Warehouse A"})

    assert response.status_code == 200
    assert response.json()["name"] == "Warehouse A"


def test_rename_rejects_a_blank_name(client):
    stored = upload(client).json()
    assert client.patch(f"/api/maps/{stored['id']}", json={"name": "   "}).status_code == 422


def test_rename_rejects_a_path_traversal_name(client):
    """The name reaches a Content-Disposition header and a download filename."""
    stored = upload(client).json()
    assert client.patch(f"/api/maps/{stored['id']}", json={"name": "../etc"}).status_code == 422


def test_rename_of_an_unknown_map_is_404(client):
    assert client.patch("/api/maps/nope", json={"name": "Warehouse B"}).status_code == 404


# ── Archive download ──────────────────────────────────────────────────────────


def test_archive_contains_both_halves_under_their_stored_names(client):
    """
    A yaml refers to its image by filename, so an archive that renamed either
    member would unzip into a map that cannot be loaded.
    """
    import io
    import zipfile

    stored = upload(client).json()

    response = client.get(f"/api/maps/{stored['id']}/archive")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == sorted([stored["yaml_file"], stored["image_file"]])
        document = pyyaml.safe_load(archive.read(stored["yaml_file"]))
        assert document["image"] == stored["image_file"]
        assert archive.read(stored["image_file"]) == pgm()


def test_archive_filename_names_the_map_and_version(client):
    stored = upload(client, name="Warehouse A").json()

    response = client.get(f"/api/maps/{stored['id']}/archive")

    assert 'filename="Warehouse_A_v1.zip"' in response.headers["content-disposition"]


def test_archive_reports_the_content_hash(client):
    """Same header as the per-file download, so a manual copy can be verified."""
    stored = upload(client).json()

    response = client.get(f"/api/maps/{stored['id']}/archive")

    assert response.headers["x-content-hash"] == hashlib.sha256(pgm()).hexdigest()


def test_archive_of_an_unknown_map_is_404(client):
    assert client.get("/api/maps/nope/archive").status_code == 404


def test_archive_reports_gone_when_the_files_vanished(client, settings):
    """A registered row whose bytes are missing is a real state after a restore."""
    stored = upload(client).json()
    for child in (settings.maps_dir / stored["id"]).iterdir():
        child.unlink()

    assert client.get(f"/api/maps/{stored['id']}/archive").status_code == 410


# ── Canonical occupancy values ────────────────────────────────────────────────
#
# A ROS map holds three states, not a greyscale range. The failure these guard
# against is silent: GIMP's default brush is feathered, so tidying a map there
# lays a band of intermediate values along every stroke. Those read as
# "unknown", which a global costmap will not plan through, and nothing in the
# file says anything is wrong.


def test_upload_accepts_the_three_canonical_values(client):
    body = bytes([OCCUPIED, UNKNOWN, FREE]) * 28
    response = upload(client, image=b"P5\n12 7\n255\n" + body)
    assert response.status_code == 201


def test_upload_refuses_an_antialiased_edge(client):
    """One soft brush stroke, expressed as the values it would leave behind."""
    body = bytearray(bytes([FREE]) * 84)
    body[10:14] = bytes([60, 120, 180, 230])  # the feathered edge
    response = upload(client, image=b"P5\n12 7\n255\n" + bytes(body))

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "4 of 84 cells" in detail
    assert "60, 120, 180, 230" in detail
    # The message has to name the cause, or the operator re-uploads the same file.
    assert "antialiasing" in detail


def test_refusal_truncates_a_long_list_of_offending_values(client):
    body = bytes(range(1, 85))  # 84 distinct non-canonical values
    detail = upload(client, image=b"P5\n12 7\n255\n" + body).json()["detail"]
    assert "…" in detail


def test_upload_refuses_a_greyscale_gradient(client):
    """What an image editor's gradient or blur filter produces."""
    body = bytes(i % 256 for i in range(84))
    assert upload(client, image=b"P5\n12 7\n255\n" + body).status_code == 422


def test_upload_refuses_an_image_that_is_not_a_pgm(client):
    assert upload(client, image=b"not an image at all").status_code == 422


def test_upload_refuses_a_pgm_truncated_mid_image(client):
    """A dropped upload must not become a map with missing cells."""
    truncated = b"P5\n12 7\n255\n" + bytes([FREE]) * 40  # needs 84
    assert upload(client, image=truncated).status_code == 422


def test_upload_accepts_ascii_pgm(client):
    """GIMP's export dialog offers ASCII, and operators do pick it."""
    body = " ".join(str(FREE) for _ in range(84))
    response = upload(client, image=f"P2\n12 7\n255\n{body}".encode())

    assert response.status_code == 201
    assert response.json()["width"] == 12


def test_ascii_pgm_is_checked_for_canonical_values_too(client):
    body = " ".join(["128"] * 84)
    assert upload(client, image=f"P2\n12 7\n255\n{body}".encode()).status_code == 422


def test_upload_accepts_a_pgm_with_a_comment_line(client):
    """map_saver does not write comments, but editors do."""
    image = b"P5\n# made by something else\n12 7\n255\n" + bytes([FREE]) * 84
    assert upload(client, image=image).status_code == 201


# ── Replacing a version in place ──────────────────────────────────────────────
#
# The riskier of the two save paths, offered because an operator correcting an
# obvious mistake does not always want a second row. What it must not do is lose
# the assignment, skip validation, or leave the files and the row disagreeing.


def replace(client, map_id, image, yaml_bytes=MAP_YAML, **form):
    return client.put(
        f"/api/maps/{map_id}/image",
        data=form,
        files={
            "yaml_file": ("map.yaml", yaml_bytes, "application/x-yaml"),
            "image_file": ("warehouse.pgm", image, "image/x-portable-graymap"),
        },
    )


def test_replace_keeps_the_id_name_and_version(client):
    before = upload(client).json()

    after = replace(client, before["id"], mixed_pgm()).json()

    assert after["id"] == before["id"]
    assert after["name"] == before["name"]
    assert after["version"] == before["version"]


def test_replace_changes_the_content_hash(client):
    """The hash is the only signal a robot has that its cached map is stale."""
    before = upload(client).json()

    after = replace(client, before["id"], mixed_pgm()).json()

    assert after["content_hash"] != before["content_hash"]
    assert after["content_hash"] == hashlib.sha256(mixed_pgm()).hexdigest()


def test_replace_does_not_create_a_second_version(client):
    stored = upload(client).json()

    replace(client, stored["id"], mixed_pgm())

    assert len(client.get("/api/maps").json()) == 1


def test_replace_keeps_an_assigned_robot_pointing_at_it(client, robot):
    """That is the appeal of replacing, and also the hazard."""
    stored = upload(client).json()
    client.put(f"/api/robots/{robot['id']}/map", json={"map_id": stored["id"]})

    replace(client, stored["id"], mixed_pgm())

    assert client.get(f"/api/robots/{robot['id']}").json()["active_map_id"] == stored["id"]


def test_replace_rewrites_the_stored_files(client, settings):
    stored = upload(client).json()

    replace(client, stored["id"], mixed_pgm())

    directory = settings.maps_dir / stored["id"]
    assert (directory / "map.pgm").read_bytes() == mixed_pgm()
    document = pyyaml.safe_load((directory / "map.yaml").read_bytes())
    assert document["image"] == "map.pgm"


def test_replace_validates_the_cells_too(client):
    """An antialiased image must not get in through the back door."""
    stored = upload(client).json()
    body = bytearray(bytes([FREE]) * 84)
    body[3:6] = bytes([80, 140, 200])

    response = replace(client, stored["id"], b"P5\n12 7\n255\n" + bytes(body))

    assert response.status_code == 422
    # The stored copy must be untouched by a refused replace.
    assert client.get(f"/api/maps/{stored['id']}").json()["content_hash"] == (
        hashlib.sha256(pgm()).hexdigest()
    )


def test_replace_updates_the_note(client):
    stored = upload(client, note="first survey").json()

    after = replace(client, stored["id"], mixed_pgm(), note="erased phantom wall").json()

    assert after["note"] == "erased phantom wall"


def test_replace_reindexes_the_geometry(client):
    """Width and height come from the new image, not the old row."""
    stored = upload(client).json()
    assert stored["width"] == 12

    after = replace(client, stored["id"], pgm(width=20, height=9, fill=FREE)).json()

    assert (after["width"], after["height"]) == (20, 9)


def test_replace_of_an_unknown_map_is_404(client):
    assert replace(client, "nope", mixed_pgm()).status_code == 404


# ---------------------------------------------------------------- upload caps


def test_oversize_yaml_is_refused_with_413(client):
    padding = b"# " + b"x" * (64 * 1024) + b"\n"
    response = upload(client, yaml_bytes=MAP_YAML + padding)
    assert response.status_code == 413
    assert client.get("/api/maps").json() == []


def test_yaml_exactly_at_the_cap_is_accepted(client):
    padding = b"#" + b"x" * (64 * 1024 - len(MAP_YAML) - 2) + b"\n"
    body = MAP_YAML + padding
    assert len(body) == 64 * 1024
    assert upload(client, yaml_bytes=body).status_code == 201


def test_oversize_image_is_refused_with_413(client, monkeypatch):
    # The real cap is 32 MiB; shrinking it keeps the test from moving that much.
    monkeypatch.setattr("app.api.maps.MAX_IMAGE_BYTES", 1024)
    response = upload(client, image=pgm(64, 64))
    assert response.status_code == 413
    assert client.get("/api/maps").json() == []


def test_replace_also_caps_both_files(client, monkeypatch):
    map_id = upload(client).json()["id"]
    monkeypatch.setattr("app.api.maps.MAX_IMAGE_BYTES", 1024)
    files = {
        "yaml_file": ("map.yaml", MAP_YAML, "application/x-yaml"),
        "image_file": ("warehouse.pgm", pgm(64, 64), "image/x-portable-graymap"),
    }
    assert client.put(f"/api/maps/{map_id}/image", files=files).status_code == 413
    files["yaml_file"] = ("map.yaml", MAP_YAML + b"#" + b"x" * 70000, "application/x-yaml")
    files["image_file"] = ("warehouse.pgm", pgm(), "image/x-portable-graymap")
    assert client.put(f"/api/maps/{map_id}/image", files=files).status_code == 413


def test_deeply_nested_yaml_is_422_not_a_crash(client):
    nested = b"image: x.pgm\ndeep: " + b"[" * 20000 + b"]" * 20000 + b"\n"
    assert len(nested) < 64 * 1024
    response = upload(client, yaml_bytes=nested)
    assert response.status_code == 422
    assert "nested" in response.json()["detail"] or "YAML" in response.json()["detail"]


def test_python_object_tags_are_not_executed(client):
    evil = b"image: x.pgm\nboom: !!python/object/apply:os.system ['true']\n"
    assert upload(client, yaml_bytes=evil).status_code == 422
