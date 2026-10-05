"""
Mission and run persistence.

A mission is a route; a run is one execution of it. They are separate tables
because they change for different reasons and at different rates — the route
when somebody edits it, the run every few seconds while a robot is moving.

SQL lives here and nowhere else, so a route handler cannot quietly invent a
query with different semantics from the rest of the application.
"""

from __future__ import annotations

import sqlite3
import uuid

_MISSION_COLUMNS = """
    id, map_id, name, note, created_at, updated_at
"""

_STEP_COLUMNS = """
    id, mission_id, ordinal, station_id, task, confirm, note
"""

_RUN_COLUMNS = """
    id, mission_id, mission_name, robot_id, mode, laps_target,
    lap, step_index, reached_lap, reached_index, reached_at,
    state, detail, started_at, ended_at, started_by
"""

LIVE_STATES = ("running", "stopping")


class DuplicateMissionError(Exception):
    """Another mission on this map already holds the name."""

    def __init__(self, name: str) -> None:
        super().__init__(f"This map already has a mission called '{name}'")
        self.name = name


class RobotBusyError(Exception):
    """The robot is already running something."""

    def __init__(self, mission_name: str) -> None:
        super().__init__(f"This robot is already running '{mission_name}'")
        self.mission_name = mission_name


def _translate(error: sqlite3.IntegrityError, name: str) -> Exception:
    message = str(error)
    if "missions.name" in message or "missions_map_name_unique" in message:
        return DuplicateMissionError(name)
    return error


# ── Missions ──────────────────────────────────────────────────────────────────


def list_missions(connection: sqlite3.Connection, map_id: str | None = None) -> list[sqlite3.Row]:
    where = "WHERE map_id = ?" if map_id else ""
    params = (map_id,) if map_id else ()
    return connection.execute(
        f"SELECT {_MISSION_COLUMNS} FROM missions {where} "  # noqa: S608 — fixed literals
        "ORDER BY name COLLATE NOCASE",
        params,
    ).fetchall()


def get_mission(connection: sqlite3.Connection, mission_id: str) -> sqlite3.Row | None:
    return connection.execute(
        f"SELECT {_MISSION_COLUMNS} FROM missions WHERE id = ?",  # noqa: S608 — fixed literal
        (mission_id,),
    ).fetchone()


def list_steps(connection: sqlite3.Connection, mission_id: str) -> list[sqlite3.Row]:
    return connection.execute(
        f"SELECT {_STEP_COLUMNS} FROM mission_steps WHERE mission_id = ? "  # noqa: S608 — fixed literal
        "ORDER BY ordinal",
        (mission_id,),
    ).fetchall()


def step_counts(connection: sqlite3.Connection) -> dict[str, int]:
    """Steps per mission, so a list does not need a query per row."""
    rows = connection.execute(
        "SELECT mission_id, COUNT(*) AS total FROM mission_steps GROUP BY mission_id"
    ).fetchall()
    return {row["mission_id"]: int(row["total"]) for row in rows}


def route_station_ids(connection: sqlite3.Connection) -> dict[str, list[str]]:
    """Each mission's stations in visiting order, so a list can preview the route."""
    rows = connection.execute(
        "SELECT mission_id, station_id FROM mission_steps ORDER BY mission_id, ordinal"
    ).fetchall()
    routes: dict[str, list[str]] = {}
    for row in rows:
        routes.setdefault(row["mission_id"], []).append(row["station_id"])
    return routes


def create_mission(connection: sqlite3.Connection, payload: dict) -> sqlite3.Row:
    mission_id = payload.get("id") or str(uuid.uuid4())
    try:
        connection.execute(
            "INSERT INTO missions (id, map_id, name, note) VALUES (:id, :map_id, :name, :note)",
            {**payload, "id": mission_id},
        )
    except sqlite3.IntegrityError as error:
        raise _translate(error, str(payload.get("name", ""))) from error

    created = get_mission(connection, mission_id)
    if created is None:  # pragma: no cover — the insert just succeeded
        raise RuntimeError("mission disappeared immediately after insert")
    return created


def update_mission(connection: sqlite3.Connection, mission_id: str, patch: dict) -> sqlite3.Row:
    if patch:
        assignments = ", ".join(f"{column} = :{column}" for column in patch)
        try:
            connection.execute(
                f"UPDATE missions SET {assignments} WHERE id = :id",  # noqa: S608 — keys are columns
                {**patch, "id": mission_id},
            )
        except sqlite3.IntegrityError as error:
            raise _translate(error, str(patch.get("name", ""))) from error

    updated = get_mission(connection, mission_id)
    if updated is None:  # pragma: no cover — checked by the caller
        raise RuntimeError("mission not found")
    return updated


def replace_steps(connection: sqlite3.Connection, mission_id: str, steps: list[dict]) -> None:
    """
    Swap the whole ordered list.

    Wholesale rather than a diff, because the thing being edited is an *order*:
    patching individual rows means shuffling ordinals past a unique index, and
    every intermediate state has to be legal. Replacing sidesteps that, and the
    caller already holds the complete list — it is what the editor renders.
    """
    connection.execute("DELETE FROM mission_steps WHERE mission_id = ?", (mission_id,))
    for index, step in enumerate(steps, start=1):
        connection.execute(
            """
            INSERT INTO mission_steps (
                id, mission_id, ordinal, station_id, task, confirm, note
            ) VALUES (
                :id, :mission_id, :ordinal, :station_id, :task, :confirm, :note
            )
            """,
            {
                "id": step.get("id") or str(uuid.uuid4()),
                "mission_id": mission_id,
                # Renumbered from the list position, so the stored order always
                # matches what was sent even if the caller left holes.
                "ordinal": index,
                "station_id": step["station_id"],
                "task": step["task"],
                "confirm": step.get("confirm", "auto"),
                "note": step.get("note"),
            },
        )


def delete_mission(connection: sqlite3.Connection, mission_id: str) -> bool:
    cursor = connection.execute("DELETE FROM missions WHERE id = ?", (mission_id,))
    return cursor.rowcount > 0


# ── Runs ──────────────────────────────────────────────────────────────────────


def active_run_for_robot(connection: sqlite3.Connection, robot_id: str) -> sqlite3.Row | None:
    placeholders = ", ".join("?" for _ in LIVE_STATES)
    return connection.execute(
        f"SELECT {_RUN_COLUMNS} FROM mission_runs "  # noqa: S608 — fixed literals
        f"WHERE robot_id = ? AND state IN ({placeholders})",
        (robot_id, *LIVE_STATES),
    ).fetchone()


def get_run(connection: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return connection.execute(
        f"SELECT {_RUN_COLUMNS} FROM mission_runs WHERE id = ?",  # noqa: S608 — fixed literal
        (run_id,),
    ).fetchone()


def list_runs(connection: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return connection.execute(
        f"SELECT {_RUN_COLUMNS} FROM mission_runs "  # noqa: S608 — fixed literal
        "ORDER BY started_at DESC, rowid DESC LIMIT ?",
        (limit,),
    ).fetchall()


def start_run(connection: sqlite3.Connection, payload: dict) -> sqlite3.Row:
    """
    Begin a run, refusing if the robot already has one.

    Checked here rather than trusted to the partial unique index alone, so the
    refusal can name what the robot is already doing instead of surfacing a
    constraint violation.
    """
    busy = active_run_for_robot(connection, payload["robot_id"])
    if busy is not None:
        raise RobotBusyError(str(busy["mission_name"]))

    run_id = payload.get("id") or str(uuid.uuid4())
    connection.execute(
        """
        INSERT INTO mission_runs (
            id, mission_id, mission_name, robot_id, mode, laps_target, started_by
        ) VALUES (
            :id, :mission_id, :mission_name, :robot_id, :mode, :laps_target, :started_by
        )
        """,
        {"started_by": None, **payload, "id": run_id},
    )
    started = get_run(connection, run_id)
    if started is None:  # pragma: no cover — the insert just succeeded
        raise RuntimeError("run disappeared immediately after insert")
    return started


def update_run(connection: sqlite3.Connection, run_id: str, patch: dict) -> sqlite3.Row:
    """
    Record progress or a terminal state.

    Written by the agent, which owns lap and step: the browser used to hold them
    in tab memory, so a refresh lost the count while the robot kept driving.
    """
    fields = dict(patch)
    if fields.get("state") in ("done", "failed", "canceled"):
        # Stamped here rather than by the caller: a terminal run with no end
        # time is a run that looks like it is still going.
        fields.setdefault("ended_at", None)
    if "reached_index" in fields:
        # The server's clock, like ended_at. It is also what makes a repeat of
        # the same step on the next lap a new arrival rather than the old one.
        fields.setdefault("reached_at", None)

    stamped = ("ended_at", "reached_at")
    assignments = ", ".join(
        f"{column} = datetime('now')" if column in stamped else f"{column} = :{column}"
        for column in fields
    )
    params = {key: value for key, value in fields.items() if key not in stamped}
    connection.execute(
        f"UPDATE mission_runs SET {assignments} WHERE id = :id",  # noqa: S608 — keys are columns
        {**params, "id": run_id},
    )
    updated = get_run(connection, run_id)
    if updated is None:  # pragma: no cover — checked by the caller
        raise RuntimeError("run not found")
    return updated
