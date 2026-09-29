"""
Map registry persistence.

The interesting part is `next_version`: two robots finishing a survey at the
same moment must not both claim version 3 of the same name. The unique index on
(name, version) makes that a constraint violation rather than a silent
duplicate, and `create_map` retries instead of failing the upload.
"""

from __future__ import annotations

import sqlite3
import uuid

_COLUMNS = """
    id, name, version, content_hash, yaml_file, image_file, image_bytes,
    resolution, width, height, origin_x, origin_y, origin_yaw,
    negate, occupied_thresh, free_thresh,
    created_by_robot_id, note, created_at
"""

# A racing writer gets a fresh version number and tries again. Three attempts
# is generous: the window is the length of one INSERT.
VERSION_RACE_ATTEMPTS = 3


class MapInUseError(Exception):
    """A map cannot be deleted while a robot or a mission still depends on it."""

    def __init__(self, robot_names: list[str], mission_names: list[str] | None = None) -> None:
        parts = []
        if robot_names:
            parts.append("assigned to " + ", ".join(robot_names))
        if mission_names:
            parts.append("used by mission " + ", ".join(mission_names))
        super().__init__("Still " + "; ".join(parts))
        self.robot_names = robot_names
        self.mission_names = mission_names or []


class MapNameTakenError(Exception):
    """Another lineage already owns the requested name."""

    def __init__(self, name: str) -> None:
        super().__init__(f"A map named '{name}' already exists")
        self.name = name


def rename_lineage(connection: sqlite3.Connection, old_name: str, new_name: str) -> int:
    """
    Rename every version that shares a name.

    Only the name column moves. Ids, files and content hashes are untouched, and
    robots reference a map by id, so a rename cannot detach a running robot from
    the map under it.
    """
    try:
        cursor = connection.execute(
            "UPDATE maps SET name = ? WHERE name = ? COLLATE NOCASE",
            (new_name, old_name),
        )
    except sqlite3.IntegrityError as error:
        # The unique index is on (name, version), so the collision is with
        # another lineage that already holds one of these version numbers.
        raise MapNameTakenError(new_name) from error
    return cursor.rowcount


def list_maps(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        f"SELECT {_COLUMNS} FROM maps "  # noqa: S608 — fixed literal
        "ORDER BY name COLLATE NOCASE, version DESC"
    ).fetchall()


def get_map(connection: sqlite3.Connection, map_id: str) -> sqlite3.Row | None:
    return connection.execute(
        f"SELECT {_COLUMNS} FROM maps WHERE id = ?",  # noqa: S608 — fixed literal
        (map_id,),
    ).fetchone()


def next_version(connection: sqlite3.Connection, name: str) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(version), 0) AS v FROM maps WHERE name = ? COLLATE NOCASE",
        (name,),
    ).fetchone()
    return int(row["v"]) + 1


def find_by_hash(
    connection: sqlite3.Connection, name: str, content_hash: str
) -> sqlite3.Row | None:
    """
    An identical image under the same name.

    Re-saving a map that has not changed should not manufacture a version that
    differs from its predecessor in nothing but its number.
    """
    return connection.execute(
        f"SELECT {_COLUMNS} FROM maps "  # noqa: S608 — fixed literal
        "WHERE name = ? COLLATE NOCASE AND content_hash = ? "
        "ORDER BY version DESC LIMIT 1",
        (name, content_hash),
    ).fetchone()


def create_map(connection: sqlite3.Connection, payload: dict) -> sqlite3.Row:
    last_error: sqlite3.IntegrityError | None = None

    for _ in range(VERSION_RACE_ATTEMPTS):
        map_id = payload.get("id") or str(uuid.uuid4())
        values = {
            **payload,
            "id": map_id,
            "version": next_version(connection, payload["name"]),
        }
        try:
            connection.execute(
                """
                INSERT INTO maps (
                    id, name, version, content_hash, yaml_file, image_file, image_bytes,
                    resolution, width, height, origin_x, origin_y, origin_yaw,
                    negate, occupied_thresh, free_thresh, created_by_robot_id, note
                ) VALUES (
                    :id, :name, :version, :content_hash, :yaml_file, :image_file, :image_bytes,
                    :resolution, :width, :height, :origin_x, :origin_y, :origin_yaw,
                    :negate, :occupied_thresh, :free_thresh, :created_by_robot_id, :note
                )
                """,
                values,
            )
        except sqlite3.IntegrityError as error:
            if "maps_name_version_unique" not in str(error):
                raise
            last_error = error
            continue

        created = get_map(connection, map_id)
        if created is None:  # pragma: no cover — the insert just succeeded
            raise RuntimeError("map disappeared immediately after insert")
        return created

    raise RuntimeError("could not allocate a map version") from last_error


def replace_image(connection: sqlite3.Connection, map_id: str, payload: dict) -> sqlite3.Row:
    """
    Replace a version's contents in place, keeping its id, name and number.

    The content hash changes, and that is the point: it is the only signal a
    robot has that a map it already holds is no longer the map it should hold.
    Nothing else about the row moves, so an assignment survives.
    """
    connection.execute(
        """
        UPDATE maps SET
            content_hash = :content_hash,
            image_file   = :image_file,
            image_bytes  = :image_bytes,
            resolution   = :resolution,
            width        = :width,
            height       = :height,
            origin_x     = :origin_x,
            origin_y     = :origin_y,
            origin_yaw   = :origin_yaw,
            negate       = :negate,
            occupied_thresh = :occupied_thresh,
            free_thresh  = :free_thresh,
            note         = :note
        WHERE id = :id
        """,
        {**payload, "id": map_id},
    )
    updated = get_map(connection, map_id)
    if updated is None:  # pragma: no cover — existence is checked by the caller
        raise RuntimeError("map disappeared during replace")
    return updated


def robots_using(connection: sqlite3.Connection, map_id: str) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM robots WHERE active_map_id = ? ORDER BY name", (map_id,)
    ).fetchall()
    return [row["name"] for row in rows]


def missions_using(connection: sqlite3.Connection, map_id: str) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM missions WHERE map_id = ? ORDER BY name COLLATE NOCASE", (map_id,)
    ).fetchall()
    return [row["name"] for row in rows]


def delete_map(connection: sqlite3.Connection, map_id: str) -> bool:
    """
    Refuses while a robot or a mission still points at the map.

    The old backend let an ordinary read delete map rows, and the cascade took
    every keepout zone, dock and destination with them. Deletion here is
    explicit, and it checks first.
    """
    # Checked rather than left to the foreign key. RESTRICT would refuse too,
    # but as an opaque constraint error that surfaces as a server fault instead
    # of a sentence naming what is in the way.
    robots = robots_using(connection, map_id)
    missions = missions_using(connection, map_id)
    if robots or missions:
        raise MapInUseError(robots, missions)

    cursor = connection.execute("DELETE FROM maps WHERE id = ?", (map_id,))
    return cursor.rowcount > 0


def assign_map(connection: sqlite3.Connection, robot_id: str, map_id: str | None) -> bool:
    cursor = connection.execute(
        "UPDATE robots SET active_map_id = ? WHERE id = ?", (map_id, robot_id)
    )
    return cursor.rowcount > 0
