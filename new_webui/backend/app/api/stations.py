"""
Station registry endpoints.

A station is a named pose in one map's frame, and the fleet's source of truth
for it lives here. The robot side keeps stations in a dictionary that empties on
every restart, so without this a site's entire layout is one power cut away from
being retyped.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import Connection
from app.db import transaction
from app.repositories import maps as maps_repo
from app.repositories import robots as robots_repo
from app.repositories import stations as repo
from app.schemas.station import StationCreate, StationOut, StationPatch

router = APIRouter(prefix="/api/stations", tags=["stations"])


def _to_out(row: sqlite3.Row) -> StationOut:
    return StationOut.model_validate(dict(row))


@router.get("", response_model=list[StationOut])
def list_stations(
    connection: Connection,
    map_id: str | None = Query(
        default=None,
        description="Only stations on this map. Omitted returns every station.",
    ),
) -> list[StationOut]:
    return [_to_out(row) for row in repo.list_stations(connection, map_id)]


@router.get("/{station_id}", response_model=StationOut)
def get_station(station_id: str, connection: Connection) -> StationOut:
    row = repo.get_station(connection, station_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found")
    return _to_out(row)


@router.post("", response_model=StationOut, status_code=status.HTTP_201_CREATED)
def create_station(body: StationCreate, connection: Connection) -> StationOut:
    """
    Register a station on a map.

    The map is checked rather than trusted: a station whose frame does not exist
    is a pose with no meaning, and the foreign key would report it as a database
    error rather than as the mistake it is.
    """
    if maps_repo.get_map(connection, body.map_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Map not found: {body.map_id}")

    if body.taught_by_robot_id is not None and (
        robots_repo.get_robot(connection, body.taught_by_robot_id) is None
    ):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Robot not found: {body.taught_by_robot_id}"
        )

    try:
        with transaction(connection):
            row = repo.create_station(connection, body.model_dump())
    except repo.DuplicateStationError as error:
        # 409 with the field named, so the form can point at the input rather
        # than showing the operator a database message.
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"field": "name", "message": str(error)}
        ) from error
    return _to_out(row)


@router.patch("/{station_id}", response_model=StationOut)
def update_station(station_id: str, body: StationPatch, connection: Connection) -> StationOut:
    """
    Change some of a station's fields.

    `exclude_unset` is what makes a dragged marker send x and y alone. Without
    it every absent field would arrive as None and wipe the stored value.
    """
    if repo.get_station(connection, station_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found")

    patch = body.model_dump(exclude_unset=True)
    if "taught_by_robot_id" in patch and patch["taught_by_robot_id"] is not None:
        if robots_repo.get_robot(connection, patch["taught_by_robot_id"]) is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Robot not found: {patch['taught_by_robot_id']}"
            )

    try:
        with transaction(connection):
            row = repo.update_station(connection, station_id, patch)
    except repo.DuplicateStationError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"field": "name", "message": str(error)}
        ) from error
    return _to_out(row)


@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_station(station_id: str, connection: Connection) -> Response:
    try:
        with transaction(connection):
            deleted = repo.delete_station(connection, station_id)
    except repo.StationInUseError as error:
        # 409, not 403: the request is well-formed and becomes legal once the
        # missions are edited. The names are carried so the UI can say which.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": str(error), "missions": error.mission_names},
        ) from error

    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
