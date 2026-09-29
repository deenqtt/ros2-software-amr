"""
Station registry persistence.

SQL lives here and nowhere else, so a route handler cannot quietly invent a
query with different semantics from the rest of the application.
"""

from __future__ import annotations

import sqlite3
import uuid

_COLUMNS = """
    id, map_id, name, type, x, y, yaw, note,
    taught_by_robot_id, created_at, updated_at
"""

# The four the robot's StationConfig.srv understands, in its own order.
STATION_TYPES = ("pick", "drop", "pick_drop", "charging")


class DuplicateStationError(Exception):
    """Another station on this map already holds the name."""

    def __init__(self, name: str) -> None:
        super().__init__(f"This map already has a station called '{name}'")
        self.name = name


def _translate(error: sqlite3.IntegrityError, name: str) -> Exception:
    # SQLite names the columns, not the index: "UNIQUE constraint failed:
    # stations.map_id, stations.name". Both spellings are matched so this
    # survives a rename of either.
    message = str(error)
    if "stations.name" in message or "stations_map_name_unique" in message:
        return DuplicateStationError(name)
    return error


class StationInUseError(Exception):
    """A station cannot be deleted while a mission step names it."""

    def __init__(self, mission_names: list[str]) -> None:
        super().__init__("Used by: " + ", ".join(mission_names))
        self.mission_names = mission_names


def missions_using(connection: sqlite3.Connection, station_id: str) -> list[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT m.name
        FROM mission_steps AS s
        JOIN missions AS m ON m.id = s.mission_id
        WHERE s.station_id = ?
        ORDER BY m.name COLLATE NOCASE
        """,
        (station_id,),
    ).fetchall()
    return [row["name"] for row in rows]


def list_stations(connection: sqlite3.Connection, map_id: str | None = None) -> list[sqlite3.Row]:
    if map_id is None:
        return connection.execute(
            f"SELECT {_COLUMNS} FROM stations "  # noqa: S608 — fixed literal
            "ORDER BY map_id, name COLLATE NOCASE"
        ).fetchall()
    return connection.execute(
        f"SELECT {_COLUMNS} FROM stations WHERE map_id = ? "  # noqa: S608 — fixed literal
        "ORDER BY name COLLATE NOCASE",
        (map_id,),
    ).fetchall()


def get_station(connection: sqlite3.Connection, station_id: str) -> sqlite3.Row | None:
    return connection.execute(
        f"SELECT {_COLUMNS} FROM stations WHERE id = ?",  # noqa: S608 — fixed literal
        (station_id,),
    ).fetchone()


def count_for_map(connection: sqlite3.Connection, map_id: str) -> int:
    """
    How many stations a map carries.

    Deleting a map cascades to these, so the delete endpoint has to be able to
    say how much goes with it rather than silently taking a site's whole layout.
    """
    row = connection.execute(
        "SELECT COUNT(*) AS total FROM stations WHERE map_id = ?", (map_id,)
    ).fetchone()
    return int(row["total"]) if row else 0


def create_station(connection: sqlite3.Connection, payload: dict) -> sqlite3.Row:
    station_id = payload.get("id") or str(uuid.uuid4())
    try:
        connection.execute(
            """
            INSERT INTO stations (
                id, map_id, name, type, x, y, yaw, note, taught_by_robot_id
            ) VALUES (
                :id, :map_id, :name, :type, :x, :y, :yaw, :note, :taught_by_robot_id
            )
            """,
            {**payload, "id": station_id},
        )
    except sqlite3.IntegrityError as error:
        raise _translate(error, str(payload.get("name", ""))) from error

    created = get_station(connection, station_id)
    if created is None:  # pragma: no cover — the insert just succeeded
        raise RuntimeError("station disappeared immediately after insert")
    return created


def update_station(connection: sqlite3.Connection, station_id: str, patch: dict) -> sqlite3.Row:
    """
    Apply only the fields present in `patch`.

    An absent key keeps the stored value; that is what makes dragging a marker a
    two-field update rather than a full rewrite that could resend a stale name.
    """
    if not patch:
        existing = get_station(connection, station_id)
        if existing is None:  # pragma: no cover — checked by the caller
            raise RuntimeError("station not found")
        return existing

    assignments = ", ".join(f"{column} = :{column}" for column in patch)
    try:
        connection.execute(
            f"UPDATE stations SET {assignments} WHERE id = :id",  # noqa: S608 — keys are column names
            {**patch, "id": station_id},
        )
    except sqlite3.IntegrityError as error:
        raise _translate(error, str(patch.get("name", ""))) from error

    updated = get_station(connection, station_id)
    if updated is None:  # pragma: no cover — checked by the caller
        raise RuntimeError("station disappeared during update")
    return updated


def delete_station(connection: sqlite3.Connection, station_id: str) -> bool:
    """
    Refuses while a mission step names it.

    The foreign key is RESTRICT, so this would fail anyway — but as an opaque
    constraint error. Checking first turns it into a sentence that names the
    missions, which is the difference between a dead end and a next step. The
    alternative, letting the delete through, produces a step that fails on the
    robot with "Unknown station_id" in front of whoever is standing there.
    """
    in_use = missions_using(connection, station_id)
    if in_use:
        raise StationInUseError(in_use)

    cursor = connection.execute("DELETE FROM stations WHERE id = ?", (station_id,))
    return cursor.rowcount > 0
