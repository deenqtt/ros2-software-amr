"""
Mission and run endpoints.

Routes are edited here; runs are dispatched here and reported back here by the
robot's agent. The browser does neither — it used to sequence waypoints from tab
memory, so closing the tab stranded a robot mid-route with nobody left to send
the next goal.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.api.deps import Connection
from app.auth import Admin, CurrentOperator, OperatorOrAgent, Principal, Reader, ensure_robot
from app.db import transaction
from app.repositories import maps as maps_repo
from app.repositories import missions as repo
from app.repositories import robots as robots_repo
from app.repositories import stations as stations_repo
from app.schemas.mission import (
    MissionCreate,
    MissionOut,
    MissionPatch,
    MissionSummary,
    RunOut,
    RunProgress,
    RunStart,
    StepIn,
    StepOut,
)

router = APIRouter(prefix="/api/missions", tags=["missions"], dependencies=[Reader])
runs_router = APIRouter(prefix="/api/runs", tags=["runs"], dependencies=[Reader])


def _to_out(connection: sqlite3.Connection, row: sqlite3.Row) -> MissionOut:
    steps = [StepOut.model_validate(dict(step)) for step in repo.list_steps(connection, row["id"])]
    return MissionOut(**dict(row), steps=steps)


def _check_steps(connection: sqlite3.Connection, map_id: str, steps: list[StepIn]) -> None:
    """
    Every step must name a station on this mission's own map.

    A station from another map would be accepted by the foreign key and fail on
    the robot, at the point where its coordinates land somewhere that does not
    exist. Checked by map, not merely by existence.
    """
    for position, step in enumerate(steps, start=1):
        station = stations_repo.get_station(connection, step.station_id)
        if station is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Step {position}: station not found"
            )
        if station["map_id"] != map_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Step {position}: station '{station['name']}' belongs to another map",
            )


# ── Missions ──────────────────────────────────────────────────────────────────


@router.get("", response_model=list[MissionSummary])
def list_missions(
    connection: Connection,
    map_id: str | None = Query(default=None, description="Only missions on this map."),
) -> list[MissionSummary]:
    counts = repo.step_counts(connection)
    routes = repo.route_station_ids(connection)
    return [
        MissionSummary(
            **dict(row),
            step_count=counts.get(row["id"], 0),
            station_ids=routes.get(row["id"], []),
        )
        for row in repo.list_missions(connection, map_id)
    ]


@router.get("/{mission_id}", response_model=MissionOut)
def get_mission(mission_id: str, connection: Connection) -> MissionOut:
    row = repo.get_mission(connection, mission_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")
    return _to_out(connection, row)


@router.post(
    "",
    response_model=MissionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Admin],
)
def create_mission(body: MissionCreate, connection: Connection) -> MissionOut:
    if maps_repo.get_map(connection, body.map_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Map not found: {body.map_id}")
    _check_steps(connection, body.map_id, body.steps)

    try:
        with transaction(connection):
            row = repo.create_mission(
                connection,
                {"map_id": body.map_id, "name": body.name, "note": body.note},
            )
            repo.replace_steps(connection, row["id"], [step.model_dump() for step in body.steps])
    except repo.DuplicateMissionError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"field": "name", "message": str(error)}
        ) from error

    return get_mission(row["id"], connection)


@router.patch("/{mission_id}", response_model=MissionOut, dependencies=[Admin])
def update_mission(mission_id: str, body: MissionPatch, connection: Connection) -> MissionOut:
    row = repo.get_mission(connection, mission_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")

    patch = body.model_dump(exclude_unset=True)
    steps = patch.pop("steps", None)
    if steps is not None:
        _check_steps(connection, str(row["map_id"]), [StepIn(**step) for step in steps])

    try:
        with transaction(connection):
            repo.update_mission(connection, mission_id, patch)
            if steps is not None:
                repo.replace_steps(connection, mission_id, steps)
    except repo.DuplicateMissionError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"field": "name", "message": str(error)}
        ) from error

    return get_mission(mission_id, connection)


@router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Admin])
def delete_mission(mission_id: str, connection: Connection) -> Response:
    """
    Remove a route.

    Runs of it survive with their mission_id cleared: what a robot did is a
    record of the floor, not of the route, and it must not disappear because
    somebody tidied up the route afterwards.
    """
    with transaction(connection):
        deleted = repo.delete_mission(connection, mission_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Runs ──────────────────────────────────────────────────────────────────────


@runs_router.get("", response_model=list[RunOut])
def list_runs(connection: Connection, limit: int = Query(default=50, ge=1, le=200)) -> list[RunOut]:
    return [RunOut.model_validate(dict(row)) for row in repo.list_runs(connection, limit)]


@runs_router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, connection: Connection) -> RunOut:
    row = repo.get_run(connection, run_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return RunOut.model_validate(dict(row))


@runs_router.post("", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def start_run(body: RunStart, operator: CurrentOperator, connection: Connection) -> RunOut:
    """
    Dispatch a mission to a robot.

    Refused when the robot already has a live run. There is no queue: a mission
    is itself an ordered list, so "do A then B" is one mission rather than two
    queued ones, and a scheduler would mostly duplicate what a mission already
    does. A clear refusal beats a queue nobody can reason about.
    """
    mission = repo.get_mission(connection, body.mission_id)
    if mission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")

    robot = robots_repo.get_robot(connection, body.robot_id)
    if robot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")

    if not repo.list_steps(connection, body.mission_id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "This mission has no steps to run"
        )

    # The robot has to be on the map the route was written against, or every
    # station in it names a place in a frame this robot is not using.
    if robot["active_map_id"] != mission["map_id"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "message": (
                    f"{robot['name']} is not on the map this mission belongs to. "
                    "Assign that map first."
                ),
                "expected_map_id": mission["map_id"],
                "actual_map_id": robot["active_map_id"],
            },
        )

    try:
        with transaction(connection):
            row = repo.start_run(
                connection,
                {
                    "mission_id": body.mission_id,
                    "mission_name": mission["name"],
                    "robot_id": body.robot_id,
                    "mode": body.mode,
                    "laps_target": body.laps_target,
                    "started_by": operator.username,
                },
            )
    except repo.RobotBusyError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": str(error), "mission": error.mission_name},
        ) from error

    return RunOut.model_validate(dict(row))


@runs_router.patch("/{run_id}", response_model=RunOut)
def update_run(
    run_id: str,
    body: RunProgress,
    request: Request,
    principal: Annotated[Principal, OperatorOrAgent],
    connection: Connection,
) -> RunOut:
    """
    Report progress, or end the run.

    Called by the robot's agent, and by the UI to ask for a stop. Setting
    `stopping` rather than a terminal state is the "finish this lap" request:
    halting mid-lap can leave a robot holding a payload it has not delivered.

    A run that has ended stays ended. The agent finishing its lap used to write
    `done` over a run the operator had canceled, so history said the route was
    completed when it had been abandoned.
    """
    current = repo.get_run(connection, run_id)
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    # An agent reports on its own robot's runs only.
    ensure_robot(principal, str(current["robot_id"]))
    if current["state"] in ("done", "failed", "canceled"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "message": f"This run has already ended ({current['state']})",
                "state": current["state"],
            },
        )

    patch = body.model_dump(exclude_unset=True)
    if principal.kind == "agent" and "state" not in patch:
        # Lap and step reports arrive constantly; the audit trail skips those,
        # but still records an agent changing the run's state.
        request.state.audit_skip = True
    if not patch:
        row = repo.get_run(connection, run_id)
        return RunOut.model_validate(dict(row))  # type: ignore[arg-type]

    with transaction(connection):
        row = repo.update_run(connection, run_id, patch)
    return RunOut.model_validate(dict(row))
