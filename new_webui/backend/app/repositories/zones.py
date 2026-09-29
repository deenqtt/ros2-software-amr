"""
Zone persistence.

SQL lives here and nowhere else, so a route handler cannot quietly invent a
query with different semantics from the rest of the application.

Polygons are stored as JSON text because SQLite has no array type. The encoding
happens here rather than in a handler, so there is one place that knows the
column is text and every reader gets the same shape back.
"""

from __future__ import annotations

import json
import sqlite3
import uuid

_COLUMNS = """
    id, map_id, name, kind, polygon, speed_limit, avoid_cost,
    enabled, note, created_at, updated_at
"""


class DuplicateZoneError(Exception):
    """Another zone on this map already holds the name."""

    def __init__(self, name: str) -> None:
        super().__init__(f"This map already has a zone called '{name}'")
        self.name = name


def _translate(error: sqlite3.IntegrityError, name: str) -> Exception:
    message = str(error)
    if "zones.name" in message or "zones_map_name_unique" in message:
        return DuplicateZoneError(name)
    return error


def _encode(payload: dict) -> dict:
    row = dict(payload)
    if "polygon" in row and not isinstance(row["polygon"], str):
        # Tuples arrive from pydantic; JSON has no tuple, so they land as lists
        # either way and come back as lists. Normalised here so a round trip is
        # the same shape it went in as.
        row["polygon"] = json.dumps([[float(x), float(y)] for x, y in row["polygon"]])
    if "enabled" in row:
        row["enabled"] = 1 if row["enabled"] else 0
    return row


def list_zones(
    connection: sqlite3.Connection,
    map_id: str | None = None,
    kind: str | None = None,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[object] = []
    if map_id:
        clauses.append("map_id = ?")
        params.append(map_id)
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return connection.execute(
        f"SELECT {_COLUMNS} FROM zones {where} "  # noqa: S608 — fixed literals
        "ORDER BY kind, name COLLATE NOCASE",
        params,
    ).fetchall()


def get_zone(connection: sqlite3.Connection, zone_id: str) -> sqlite3.Row | None:
    return connection.execute(
        f"SELECT {_COLUMNS} FROM zones WHERE id = ?",  # noqa: S608 — fixed literal
        (zone_id,),
    ).fetchone()


def count_for_map(connection: sqlite3.Connection, map_id: str) -> int:
    """How many zones go with a map, so a delete can say what else is at stake."""
    row = connection.execute(
        "SELECT COUNT(*) AS total FROM zones WHERE map_id = ?", (map_id,)
    ).fetchone()
    return int(row["total"]) if row else 0


def create_zone(connection: sqlite3.Connection, payload: dict) -> sqlite3.Row:
    zone_id = payload.get("id") or str(uuid.uuid4())
    try:
        connection.execute(
            """
            INSERT INTO zones (
                id, map_id, name, kind, polygon, speed_limit, avoid_cost, enabled, note
            ) VALUES (
                :id, :map_id, :name, :kind, :polygon, :speed_limit, :avoid_cost,
                :enabled, :note
            )
            """,
            {**_encode(payload), "id": zone_id},
        )
    except sqlite3.IntegrityError as error:
        raise _translate(error, str(payload.get("name", ""))) from error

    created = get_zone(connection, zone_id)
    if created is None:  # pragma: no cover — the insert just succeeded
        raise RuntimeError("zone disappeared immediately after insert")
    return created


def update_zone(connection: sqlite3.Connection, zone_id: str, patch: dict) -> sqlite3.Row:
    if patch:
        encoded = _encode(patch)
        assignments = ", ".join(f"{column} = :{column}" for column in encoded)
        try:
            connection.execute(
                f"UPDATE zones SET {assignments} WHERE id = :id",  # noqa: S608 — keys are columns
                {**encoded, "id": zone_id},
            )
        except sqlite3.IntegrityError as error:
            raise _translate(error, str(patch.get("name", ""))) from error

    updated = get_zone(connection, zone_id)
    if updated is None:  # pragma: no cover — checked by the caller
        raise RuntimeError("zone not found")
    return updated


def delete_zone(connection: sqlite3.Connection, zone_id: str) -> bool:
    cursor = connection.execute("DELETE FROM zones WHERE id = ?", (zone_id,))
    return cursor.rowcount > 0
