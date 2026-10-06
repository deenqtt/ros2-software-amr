"""
Robot registry endpoints.

The frontend keeps its registry in localStorage today, which means it is
per-browser: open the console on a second laptop and there are no robots. This
is what replaces that.
"""

from __future__ import annotations

import secrets
import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import Connection
from app.api.missions import run_in_progress
from app.auth import (
    Admin,
    AdminOrAgent,
    OperatorOrAgent,
    Principal,
    Reader,
    ensure_robot,
)
from app.db import transaction
from app.repositories import maps as maps_repo
from app.repositories import missions as missions_repo
from app.repositories import robots as repo
from app.schemas.map import AssignMapIn
from app.schemas.mission import RunPlan, StepOut
from app.schemas.robot import AgentTokenOut, RobotCreate, RobotOut, RobotUpdate, SetModeIn
from app.security import hash_token

router = APIRouter(prefix="/api/robots", tags=["robots"], dependencies=[Reader])


def _to_out(row: sqlite3.Row) -> RobotOut:
    return RobotOut.model_validate(dict(row))


@router.get("", response_model=list[RobotOut])
def list_robots(connection: Connection) -> list[RobotOut]:
    return [_to_out(row) for row in repo.list_robots(connection)]


@router.get("/{robot_id}", response_model=RobotOut)
def get_robot(
    robot_id: str,
    connection: Connection,
) -> RobotOut:
    row = repo.get_robot(connection, robot_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")
    return _to_out(row)


@router.post("", response_model=RobotOut, status_code=status.HTTP_201_CREATED, dependencies=[Admin])
def create_robot(
    body: RobotCreate,
    connection: Connection,
) -> RobotOut:
    try:
        with transaction(connection):
            row = repo.create_robot(connection, body.model_dump())
    except repo.DuplicateRobotError as error:
        # 409, not 400: the request is well-formed, it conflicts with state.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"field": error.field, "message": str(error)},
        ) from error
    return _to_out(row)


@router.patch("/{robot_id}", response_model=RobotOut, dependencies=[Admin])
def update_robot(
    robot_id: str,
    body: RobotUpdate,
    connection: Connection,
) -> RobotOut:
    """
    PATCH, not PUT.

    ``exclude_unset`` is what makes "omitted" mean "leave alone" while an
    explicit ``null`` still clears a nullable field (a null for a NOT NULL
    one is a 422, see RobotUpdate). The old API used PUT with a full
    model, so any field the client forgot to resend was reset to its default —
    which is how changing a destination's type wiped its yaw.
    """
    patch = body.model_dump(exclude_unset=True)
    try:
        with transaction(connection):
            row = repo.update_robot(connection, robot_id, patch)
    except repo.DuplicateRobotError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"field": error.field, "message": str(error)},
        ) from error

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")
    return _to_out(row)


@router.delete("/{robot_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Admin])
def delete_robot(
    robot_id: str,
    connection: Connection,
) -> Response:
    """
    Remove a robot from the registry.

    Refused with 409 while it has a live run (running or stopping): the run's
    robot would be cleared, leaving a run nobody can report on or stop from
    here while the robot itself may still be driving it. Stop the run first.
    """
    with transaction(connection):
        live = missions_repo.active_run_for_robot(connection, robot_id)
        if live is not None:
            raise run_in_progress(live, "delete the robot")
        deleted = repo.delete_robot(connection, robot_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{robot_id}/mode", response_model=RobotOut)
def set_mode(
    robot_id: str,
    body: SetModeIn,
    principal: Annotated[Principal, OperatorOrAgent],
    connection: Connection,
) -> RobotOut:
    """
    Say what this robot should be doing.

    Intent, not a command. The agent reconciles towards it at every sync, so a
    robot that restarts comes back to work instead of coming back idle — which
    is what happened before this existed, with nothing anywhere reporting it.

    `nav` is the resting state and the default. Nav2 running is not the robot
    moving: an idle planner plans nothing, and the robot only moves when a
    mission gives it a goal.
    """
    ensure_robot(principal, robot_id)
    if repo.get_robot(connection, robot_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")

    with transaction(connection):
        repo.set_desired_mode(connection, robot_id, body.desired_mode)

    row = repo.get_robot(connection, robot_id)
    if row is None:  # pragma: no cover — existence was just checked
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")
    return _to_out(row)


@router.get("/{robot_id}/run", response_model=RunPlan | None)
def get_active_run(
    robot_id: str,
    principal: Annotated[Principal, Reader],
    connection: Connection,
) -> RunPlan | None:
    """
    What this robot should be doing, or null.

    Read by the robot's own agent, which is the only thing that executes a
    mission. The browser used to sequence waypoints from tab memory, so closing
    it stranded a robot mid-route with nobody left to send the next goal; this
    is the call that replaces that, and it is also how an agent that has just
    restarted discovers it was in the middle of something.
    """
    ensure_robot(principal, robot_id)
    if repo.get_robot(connection, robot_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")

    run = missions_repo.active_run_for_robot(connection, robot_id)
    if run is None:
        return None

    steps = [
        StepOut.model_validate(dict(step))
        for step in missions_repo.list_steps(connection, str(run["mission_id"]))
    ]
    return RunPlan(**dict(run), steps=steps)


@router.put("/{robot_id}/map", response_model=RobotOut)
def assign_map(
    robot_id: str,
    body: AssignMapIn,
    principal: Annotated[Principal, AdminOrAgent],
    connection: Connection,
) -> RobotOut:
    """
    Point a robot at a map.

    Assignment is per robot, not global. Two robots in one building normally
    share a map — they have to, or a station at (12.4, 3.1) names a different
    physical place for each of them — but one being re-surveyed while the other
    keeps working is exactly the case a global setting cannot express.

    The robot's agent notices the change, compares the map's content hash
    against its local cache, downloads if needed, and calls
    /map_server/load_map with a path on its own disk.
    """
    ensure_robot(principal, robot_id)
    if repo.get_robot(connection, robot_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")

    if body.map_id is not None and maps_repo.get_map(connection, body.map_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Map not found: {body.map_id}")

    with transaction(connection):
        maps_repo.assign_map(connection, robot_id, body.map_id)

    row = repo.get_robot(connection, robot_id)
    if row is None:  # pragma: no cover — existence was just checked
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")
    return _to_out(row)


@router.post(
    "/{robot_id}/agent-token",
    response_model=AgentTokenOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Admin],
)
def mint_agent_token(robot_id: str, response: Response, connection: Connection) -> AgentTokenOut:
    """
    Issue this robot's agent token, replacing any it had.

    Shown once: only its hash is stored, so a lost token is replaced, not
    recovered. Calling this again is the rotation — the previous token stops
    working as soon as the new one is stored. A person only: an agent cannot
    mint itself a new credential.
    """
    token = secrets.token_urlsafe(32)
    with transaction(connection):
        updated = repo.set_agent_token(connection, robot_id, hash_token(token))
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")

    row = repo.get_robot(connection, robot_id)
    if row is None:  # pragma: no cover — it was just updated
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return AgentTokenOut(token=token, created_at=str(row["agent_token_created_at"]))


@router.delete(
    "/{robot_id}/agent-token", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Admin]
)
def revoke_agent_token(robot_id: str, connection: Connection) -> Response:
    """Revoke this robot's agent token. Its agent is refused until a new one is issued."""
    with transaction(connection):
        updated = repo.clear_agent_token(connection, robot_id)
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
