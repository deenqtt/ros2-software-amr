"""
Request and response models for zones.

A zone is an area of a map that changes how a robot behaves inside it. Nav2
enforces them through costmap filters, and there are exactly three of those —
so there are four kinds here, two of which share a filter and differ only in the
value written into its mask.

Polygons are carried as points, never as the rasterised mask. The mask belongs
to one map resolution and cannot be edited back into corners; the polygon is
what the operator drew.
"""

from __future__ import annotations

import json
import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.patch import reject_nulls

NAME_MAX = 64

#: keepout and avoid are the same Nav2 filter; only the mask value differs.
ZoneKind = Literal["keepout", "avoid", "speed", "binary"]

# Three points make an area; two make a line with none.
MIN_POINTS = 3
# A rail against a runaway client, not a limit anybody will meet by hand: a
# polygon traced around a warehouse aisle is a dozen points.
MAX_POINTS = 500

ZoneName = Annotated[str, Field(min_length=1, max_length=NAME_MAX)]

#: Metres in the map frame. Never pixels — a re-survey at a finer resolution
#: must not move a zone.
Point = tuple[float, float]


def _check_polygon(points: list[Point]) -> list[Point]:
    if len(points) < MIN_POINTS:
        raise ValueError(f"a zone needs at least {MIN_POINTS} points to enclose an area")
    if len(points) > MAX_POINTS:
        raise ValueError(f"a zone may not have more than {MAX_POINTS} points")
    for index, point in enumerate(points):
        for value in point:
            # NaN survives JSON and then poisons the rasteriser in silence,
            # producing a mask with no zone in it and no error anywhere.
            if not math.isfinite(value):
                raise ValueError(f"point {index + 1} is not a finite coordinate")
    return points


class ZoneBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ZoneName
    kind: ZoneKind
    polygon: list[Point]
    speed_limit: Annotated[float, Field(gt=0, le=10)] | None = None
    avoid_cost: Annotated[int, Field(ge=1, le=99)] | None = None
    enabled: bool = True
    note: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped

    @field_validator("polygon")
    @classmethod
    def _validate_polygon(cls, value: list[Point]) -> list[Point]:
        return _check_polygon(value)

    @model_validator(mode="after")
    def _settings_match_the_kind(self) -> ZoneBase:
        # A model validator, not field ones: a field validator never fires for a
        # key that was left out, so `kind: speed` with no limit would sail
        # through and produce a zone that restricts nothing.
        if self.kind == "speed" and self.speed_limit is None:
            raise ValueError("speed_limit is required for a speed zone")
        if self.kind != "speed" and self.speed_limit is not None:
            raise ValueError("speed_limit only applies to a speed zone")
        if self.kind == "avoid" and self.avoid_cost is None:
            raise ValueError("avoid_cost is required for an avoid zone")
        if self.kind != "avoid" and self.avoid_cost is not None:
            raise ValueError("avoid_cost only applies to an avoid zone")
        return self


class ZoneCreate(ZoneBase):
    map_id: str


#: The only zone columns a PATCH may clear with an explicit null.
PATCH_NULLABLE = frozenset({"speed_limit", "avoid_cost", "note"})


class ZonePatch(BaseModel):
    """
    Partial update. Omitted is not null: a key left out keeps the stored value.

    Changing `kind` means the settings that go with it change too, so a patch
    that touches any of kind, speed_limit or avoid_cost is validated as a whole
    against the stored row — see the endpoint.

    Only the nullable columns (speed_limit, avoid_cost, note) may be sent as
    null. `enabled: null` used to be stored as 0 and switch a keep-out zone off
    without anybody asking for that.
    """

    model_config = ConfigDict(extra="forbid")

    name: ZoneName | None = None
    kind: ZoneKind | None = None
    polygon: list[Point] | None = None
    speed_limit: Annotated[float, Field(gt=0, le=10)] | None = None
    avoid_cost: Annotated[int, Field(ge=1, le=99)] | None = None
    enabled: bool | None = None
    note: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped

    @field_validator("polygon")
    @classmethod
    def _validate_polygon(cls, value: list[Point] | None) -> list[Point] | None:
        return None if value is None else _check_polygon(value)

    @model_validator(mode="after")
    def _no_null_on_required(self) -> ZonePatch:
        reject_nulls(self, PATCH_NULLABLE)
        return self


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    map_id: str
    name: str
    kind: ZoneKind
    polygon: list[Point]
    speed_limit: float | None
    avoid_cost: int | None
    enabled: bool
    note: str | None
    created_at: str
    updated_at: str

    @field_validator("polygon", mode="before")
    @classmethod
    def _decode(cls, value: object) -> object:
        # Stored as JSON text, because SQLite has no array type.
        if isinstance(value, str):
            return json.loads(value)
        return value
