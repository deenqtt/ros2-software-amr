"""
Request and response models for the station registry.

A station is a named pose in one map's frame. Everything here is expressed in
that frame — metres and radians, as Nav2 wants them — and never in pixels: a
pixel is a property of the image, and the image can be re-surveyed at a
different resolution while the shelf stays where it is.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

NAME_MAX = 64

StationName = Annotated[str, Field(min_length=1, max_length=NAME_MAX)]

# Mirrors the robot's StationConfig.srv enum (0=Pick, 1=Drop, 2=Pick&Drop,
# 3=Charging) in a form a person can read. The agent maps it to the number.
StationType = Literal["pick", "drop", "pick_drop", "charging"]

TYPE_TO_WIRE: dict[str, int] = {"pick": 0, "drop": 1, "pick_drop": 2, "charging": 3}


def _finite(value: float, field: str) -> float:
    # NaN and infinity survive JSON parsing and then poison every distance
    # calculation downstream in silence.
    if not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return value


class StationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StationName
    type: StationType
    x: float
    y: float
    yaw: float
    note: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped

    @field_validator("x", "y", "yaw")
    @classmethod
    def _check_finite(cls, value: float, info) -> float:
        return _finite(value, info.field_name)


class StationCreate(StationBase):
    """
    A new station on one map.

    `map_id` names a specific version, not a lineage. A pixel edit leaves origin
    and resolution alone so coordinates survive it, but a fresh survey produces a
    new origin — and a station carried blindly across that points at the wrong
    place while looking entirely valid.
    """

    map_id: str
    taught_by_robot_id: str | None = None


class StationPatch(BaseModel):
    """
    Partial update.

    Every key is optional and *omitted is not null*: leaving a key out keeps the
    stored value. That is what lets dragging a marker send x and y alone rather
    than a whole record that might carry a stale name.
    """

    model_config = ConfigDict(extra="forbid")

    name: StationName | None = None
    type: StationType | None = None
    x: float | None = None
    y: float | None = None
    yaw: float | None = None
    note: str | None = None
    taught_by_robot_id: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped

    @field_validator("x", "y", "yaw")
    @classmethod
    def _check_finite(cls, value: float | None, info) -> float | None:
        return None if value is None else _finite(value, info.field_name)


class StationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    map_id: str
    name: str
    type: StationType
    x: float
    y: float
    yaw: float
    note: str | None
    taught_by_robot_id: str | None
    created_at: str
    updated_at: str
