"""
Robot registry persistence.

SQL lives here and nowhere else, so a route handler cannot quietly invent a
query with different semantics from the rest of the application.
"""

from __future__ import annotations

import sqlite3
import uuid

ACCENT_COUNT = 8

_COLUMNS = """
    id, name, bridge_url, ros_domain_id, camera_url,
    namespace, serial, accent, active_map_id, desired_mode, created_at, updated_at
"""


class DuplicateRobotError(Exception):
    """A unique constraint rejected the write. Carries the offending field."""

    def __init__(self, field: str, value: str) -> None:
        super().__init__(f"Another robot already uses this {field}: {value}")
        self.field = field
        self.value = value


# SQLite reports a unique-index violation by *column*, not by index name:
# "UNIQUE constraint failed: robots.name". Both spellings are matched so the
# translation survives a future rename of either the index or the column.
_UNIQUE_FIELDS = {
    "name": ("robots.name", "robots_name_unique"),
    "bridge_url": ("robots.bridge_url", "robots_bridge_unique"),
}


def _translate_integrity_error(error: sqlite3.IntegrityError, payload: dict) -> Exception:
    """Turn an opaque constraint failure into something a client can act on."""
    message = str(error)
    for field, markers in _UNIQUE_FIELDS.items():
        if any(marker in message for marker in markers):
            return DuplicateRobotError(field, str(payload.get(field, "")))
    return error


def next_accent(connection: sqlite3.Connection) -> int:
    """
    Lowest accent colour not currently in use.

    Accents are identity, so reusing one while its robot still exists would
    make two machines look alike in the one place that must not be ambiguous.
    """
    rows = connection.execute("SELECT accent FROM robots").fetchall()
    taken = {row["accent"] for row in rows}
    for accent in range(1, ACCENT_COUNT + 1):
        if accent not in taken:
            return accent
    # More robots than colours: wrap, and let the name carry the distinction.
    return (len(taken) % ACCENT_COUNT) + 1


def list_robots(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        f"SELECT {_COLUMNS} FROM robots ORDER BY name COLLATE NOCASE"  # noqa: S608 — fixed literal
    ).fetchall()


def get_robot(connection: sqlite3.Connection, robot_id: str) -> sqlite3.Row | None:
    return connection.execute(
        f"SELECT {_COLUMNS} FROM robots WHERE id = ?",  # noqa: S608 — fixed literal
        (robot_id,),
    ).fetchone()


def create_robot(connection: sqlite3.Connection, payload: dict) -> sqlite3.Row:
    robot_id = str(uuid.uuid4())
    values = {
        "id": robot_id,
        "accent": next_accent(connection),
        **payload,
    }
    try:
        connection.execute(
            """
            INSERT INTO robots
                (id, name, bridge_url, ros_domain_id, camera_url, namespace, serial, accent)
            VALUES
                (:id, :name, :bridge_url, :ros_domain_id, :camera_url, :namespace, :serial, :accent)
            """,
            values,
        )
    except sqlite3.IntegrityError as error:
        raise _translate_integrity_error(error, values) from error

    created = get_robot(connection, robot_id)
    if created is None:  # pragma: no cover — the insert just succeeded.
        raise RuntimeError("robot disappeared immediately after insert")
    return created


def update_robot(connection: sqlite3.Connection, robot_id: str, patch: dict) -> sqlite3.Row | None:
    """
    Apply a partial update.

    ``patch`` must contain only the fields the caller actually sent. A key that
    is absent is left alone; a key present with ``None`` is written as NULL.
    That distinction is the whole point — the old API could not express it, so
    a PUT that omitted a field silently reset it to a default.
    """
    if get_robot(connection, robot_id) is None:
        return None
    if not patch:
        return get_robot(connection, robot_id)

    assignments = ", ".join(f"{column} = :{column}" for column in patch)
    try:
        connection.execute(
            f"UPDATE robots SET {assignments} WHERE id = :id",  # noqa: S608 — keys are validated
            {**patch, "id": robot_id},
        )
    except sqlite3.IntegrityError as error:
        raise _translate_integrity_error(error, patch) from error

    return get_robot(connection, robot_id)


def set_desired_mode(connection: sqlite3.Connection, robot_id: str, mode: str) -> bool:
    """
    Record what this robot should be doing.

    Separate from update_robot because it is a control action rather than an
    edit of the record: it changes what happens on the floor, and a handler that
    could set it as a side effect of renaming would be a surprise.
    """
    cursor = connection.execute(
        "UPDATE robots SET desired_mode = ? WHERE id = ?", (mode, robot_id)
    )
    return cursor.rowcount > 0


def delete_robot(connection: sqlite3.Connection, robot_id: str) -> bool:
    cursor = connection.execute("DELETE FROM robots WHERE id = ?", (robot_id,))
    return cursor.rowcount > 0


def count_robots(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) AS total FROM robots").fetchone()
    return int(row["total"])
