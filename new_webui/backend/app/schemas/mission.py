"""
Request and response models for missions and their runs.

A mission is a route; a run is one execution of it. Looping is a property of the
run, not of the route: the same "Pickup A, then Dropoff" is sometimes a one-off
delivery and sometimes a shift of shuttling, and putting `loop` on the route
forces two near-identical missions that drift apart the moment one is edited.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NAME_MAX = 64
# A rail, not a rule. The previous UI capped routes at five steps with no reason
# recorded; this is high enough never to be met by a real route and low enough
# that a runaway client cannot write a million rows.
MAX_STEPS = 50

MissionName = Annotated[str, Field(min_length=1, max_length=NAME_MAX)]

#: MissionPlan.action dest_tasks. `none` is a waypoint merely passed through.
StepTask = Literal["none", "pick", "drop"]
TASK_TO_WIRE: dict[str, int] = {"none": 0, "pick": 1, "drop": 2}

#: MissionPlan.action continue_mode, spelled out. `confirm` waits for
#: /mission_confirm, which means somebody has to be standing there.
StepConfirm = Literal["auto", "confirm"]

RunMode = Literal["once", "laps", "forever"]
RunState = Literal["running", "stopping", "done", "failed", "canceled"]


class StepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_id: str
    task: StepTask = "none"
    confirm: StepConfirm = "auto"
    note: str | None = None


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ordinal: int
    station_id: str
    task: StepTask
    confirm: StepConfirm
    note: str | None


class MissionCreate(BaseModel):
    """
    A route on one map.

    Steps arrive as an ordered list and are numbered from their position, so the
    client never has to manage ordinals — it sends what the editor shows.
    """

    model_config = ConfigDict(extra="forbid")

    map_id: str
    name: MissionName
    note: str | None = None
    steps: Annotated[list[StepIn], Field(max_length=MAX_STEPS)] = []

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped


class MissionPatch(BaseModel):
    """
    Partial update. Omitted is not null: a key left out keeps the stored value.

    `steps` is all-or-nothing by design — the thing being edited is an order, and
    patching rows individually means shuffling ordinals past a unique index with
    every intermediate state having to be legal.
    """

    model_config = ConfigDict(extra="forbid")

    name: MissionName | None = None
    note: str | None = None
    steps: Annotated[list[StepIn], Field(max_length=MAX_STEPS)] | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped


class MissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    map_id: str
    name: str
    note: str | None
    steps: list[StepOut] = []
    created_at: str
    updated_at: str


class MissionSummary(BaseModel):
    """A list row: everything but the steps, plus how many there are."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    map_id: str
    name: str
    note: str | None
    step_count: int
    # Station ids in visiting order: enough to draw the route, without the steps.
    station_ids: list[str] = []
    created_at: str
    updated_at: str


class RunStart(BaseModel):
    """
    Dispatch a mission to a robot.

    `laps_target` belongs to `laps` and to nothing else: a count without a
    looping mode is a number nobody reads, and `laps` without a count is not a
    number of laps.
    """

    model_config = ConfigDict(extra="forbid")

    mission_id: str
    robot_id: str
    mode: RunMode = "once"
    laps_target: Annotated[int, Field(ge=1, le=10_000)] | None = None

    @model_validator(mode="after")
    def _laps_needs_a_count(self) -> RunStart:
        # A *model* validator, not a field one: a field validator never fires
        # for a key that was left out, so `mode: laps` with no count sailed
        # through and produced a run that loops an unstated number of times.
        if self.mode == "laps" and self.laps_target is None:
            raise ValueError("laps_target is required when mode is 'laps'")
        if self.mode != "laps" and self.laps_target is not None:
            raise ValueError("laps_target only applies when mode is 'laps'")
        return self


class RunProgress(BaseModel):
    """
    Written by the robot's agent as it works through the route.

    The agent owns these, not the browser. A refresh used to lose the lap count
    while the robot kept driving.
    """

    model_config = ConfigDict(extra="forbid")

    lap: Annotated[int, Field(ge=1)] | None = None
    step_index: Annotated[int, Field(ge=0)] | None = None
    #: An arrival, reported when Nav2 says the step succeeded. The server stamps
    #: the time, so the same step on the next lap is still a new arrival.
    reached_lap: Annotated[int, Field(ge=1)] | None = None
    reached_index: Annotated[int, Field(ge=0)] | None = None
    state: RunState | None = None
    detail: str | None = None


class RunPlan(BaseModel):
    """
    Everything a robot's agent needs to execute a run, in one reply.

    The steps are resolved and inlined rather than referenced, because the agent
    fetching them separately would leave a window where the route changed
    between the two calls — and it would be executing half of each.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    mission_name: str
    mode: RunMode
    laps_target: int | None
    lap: int
    step_index: int
    state: RunState
    #: Ordered. Station ids are what the robot was registered under.
    steps: list[StepOut]


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mission_id: str | None
    #: Kept alongside the id so history stays readable after a route is deleted.
    mission_name: str
    robot_id: str | None
    mode: RunMode
    laps_target: int | None
    lap: int
    step_index: int
    #: The last stop actually arrived at. Null until the first arrival.
    reached_lap: int | None = None
    reached_index: int | None = None
    reached_at: str | None = None
    state: RunState
    detail: str | None
    started_at: str
    ended_at: str | None
