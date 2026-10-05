"""
Zone endpoints.

A zone is an area of a map that changes how a robot behaves inside it. The
registry holds the polygons; a robot's agent turns them into the costmap filter
masks Nav2 actually reads, the same arrangement maps and stations already use.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import Connection
from app.auth import Admin, Reader
from app.db import transaction
from app.repositories import maps as maps_repo
from app.repositories import zones as repo
from app.schemas.zone import ZoneCreate, ZoneKind, ZoneOut, ZonePatch

router = APIRouter(prefix="/api/zones", tags=["zones"], dependencies=[Reader])


def _to_out(row: sqlite3.Row) -> ZoneOut:
    return ZoneOut.model_validate(dict(row))


def _check_settings(kind: str, speed_limit: float | None, avoid_cost: int | None) -> None:
    """
    The settings a kind requires, and the ones it has no use for.

    Checked here as well as in the create model because a patch may change the
    kind without resending the settings — and the database constraint would
    report that as an opaque failure rather than as the mistake it is.
    """
    if kind == "speed" and speed_limit is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "speed_limit is required for a speed zone"
        )
    if kind != "speed" and speed_limit is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "speed_limit only applies to a speed zone"
        )
    if kind == "avoid" and avoid_cost is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "avoid_cost is required for an avoid zone"
        )
    if kind != "avoid" and avoid_cost is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "avoid_cost only applies to an avoid zone"
        )


@router.get("", response_model=list[ZoneOut])
def list_zones(
    connection: Connection,
    map_id: Annotated[str | None, Query(description="Only zones on this map.")] = None,
    kind: Annotated[ZoneKind | None, Query(description="Only zones of this kind.")] = None,
) -> list[ZoneOut]:
    return [_to_out(row) for row in repo.list_zones(connection, map_id, kind)]


@router.get("/{zone_id}", response_model=ZoneOut)
def get_zone(zone_id: str, connection: Connection) -> ZoneOut:
    row = repo.get_zone(connection, zone_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zone not found")
    return _to_out(row)


@router.post("", response_model=ZoneOut, status_code=status.HTTP_201_CREATED, dependencies=[Admin])
def create_zone(body: ZoneCreate, connection: Connection) -> ZoneOut:
    if maps_repo.get_map(connection, body.map_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Map not found: {body.map_id}")

    try:
        with transaction(connection):
            row = repo.create_zone(connection, body.model_dump())
    except repo.DuplicateZoneError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"field": "name", "message": str(error)}
        ) from error
    return _to_out(row)


@router.patch("/{zone_id}", response_model=ZoneOut, dependencies=[Admin])
def update_zone(zone_id: str, body: ZonePatch, connection: Connection) -> ZoneOut:
    """
    Change some of a zone's fields.

    `exclude_unset` is what lets a reshaped polygon travel alone. Without it
    every absent field would arrive as None and clear the stored value — which
    for `kind` would leave a zone that is not any kind of zone.
    """
    row = repo.get_zone(connection, zone_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zone not found")

    patch = body.model_dump(exclude_unset=True)

    # The kind and its settings are checked together against what the row will
    # be *after* the patch, not against what was sent: switching a speed zone to
    # a keepout has to drop the limit, and the client may not resend either.
    if {"kind", "speed_limit", "avoid_cost"} & patch.keys():
        merged = {
            "kind": patch.get("kind", row["kind"]),
            "speed_limit": patch.get("speed_limit", row["speed_limit"]),
            "avoid_cost": patch.get("avoid_cost", row["avoid_cost"]),
        }
        if "kind" in patch and patch["kind"] != row["kind"]:
            # A setting the new kind has no use for is cleared rather than
            # refused: the operator asked for a different kind of zone, and the
            # old number is not a thing they need to delete by hand first.
            if merged["kind"] != "speed" and "speed_limit" not in patch:
                merged["speed_limit"] = patch["speed_limit"] = None
            if merged["kind"] != "avoid" and "avoid_cost" not in patch:
                merged["avoid_cost"] = patch["avoid_cost"] = None
        _check_settings(str(merged["kind"]), merged["speed_limit"], merged["avoid_cost"])

    try:
        with transaction(connection):
            updated = repo.update_zone(connection, zone_id, patch)
    except repo.DuplicateZoneError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"field": "name", "message": str(error)}
        ) from error
    return _to_out(updated)


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Admin])
def delete_zone(zone_id: str, connection: Connection) -> Response:
    with transaction(connection):
        deleted = repo.delete_zone(connection, zone_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zone not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
