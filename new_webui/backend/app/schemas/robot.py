"""
Request and response models for the robot registry.

Every field the client sends is declared here. The previous contract dropped
whatever it had not declared — missions lost ``station_id`` and ``dest_point``,
docks lost their entire approach pose — because Pydantic ignores unknown keys
by default and nothing objected. These models forbid extra fields instead, so a
client sending something the server does not understand gets told.
"""

from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

NAME_MAX = 64
ROS_DOMAIN_ID_MAX = 232
# Above this, a domain can collide with ephemeral ports on some systems. It is
# allowed, because a fleet may already use it, but the UI warns.
ROS_DOMAIN_ID_SAFE_MAX = 101

RobotName = Annotated[str, Field(min_length=1, max_length=NAME_MAX)]
RosDomainId = Annotated[int, Field(ge=0, le=ROS_DOMAIN_ID_MAX)]
Accent = Annotated[int, Field(ge=1, le=8)]

#: What a robot is supposed to be doing, as opposed to what it is doing.
#:
#: `nav` is the resting state: Nav2 up, waiting for goals. It is not the robot
#: moving — an idle planner plans nothing, and the robot only moves when a
#: mission gives it a goal. `map` and `nav` are exclusive because SLAM and Nav2
#: both own /map. `idle` is a choice — parked, or being worked on.
DesiredMode = Literal["nav", "idle", "map"]


def _validate_bridge_url(value: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"ws", "wss"}:
        raise ValueError("bridge_url must start with ws:// or wss://")
    if not parsed.hostname:
        raise ValueError("bridge_url is missing a host")
    return url


class RobotBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RobotName
    bridge_url: str
    ros_domain_id: RosDomainId | None = None
    camera_url: str | None = None
    namespace: str = ""
    serial: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped

    @field_validator("bridge_url")
    @classmethod
    def _check_bridge(cls, value: str) -> str:
        return _validate_bridge_url(value)

    @field_validator("namespace")
    @classmethod
    def _normalise_namespace(cls, value: str) -> str:
        return value.strip().strip("/")


class RobotCreate(RobotBase):
    """Accent is assigned by the server, so the client does not send one."""


class RobotUpdate(BaseModel):
    """
    Partial update. Every field is optional, and *omitted is not the same as
    null*: omitting ``ros_domain_id`` leaves it alone, sending ``null`` clears
    it. The old API had no way to express that difference, so a PUT that did
    not mention a field silently reset it — which is how changing a
    destination's type wiped its orientation.
    """

    model_config = ConfigDict(extra="forbid")

    name: RobotName | None = None
    bridge_url: str | None = None
    ros_domain_id: RosDomainId | None = None
    camera_url: str | None = None
    namespace: str | None = None
    serial: str | None = None
    accent: Accent | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped

    @field_validator("bridge_url")
    @classmethod
    def _check_bridge(cls, value: str | None) -> str | None:
        return None if value is None else _validate_bridge_url(value)


class RobotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    bridge_url: str
    ros_domain_id: int | None
    camera_url: str | None
    namespace: str
    serial: str | None
    accent: int
    # Which map this robot is meant to be running. The agent reconciles its
    # local cache against it; null means no map assigned yet.
    active_map_id: str | None
    # What it is *supposed* to be doing. The agent reconciles towards this, so
    # a robot that restarts comes back to work rather than coming back idle.
    desired_mode: DesiredMode
    created_at: str
    updated_at: str
    # Whether this robot's agent has a token, and since when. The token itself
    # is shown once, when minted, and its hash never leaves the database.
    agent_token_set: bool = False
    agent_token_created_at: str | None = None


class AgentTokenOut(BaseModel):
    """
    A freshly minted agent token. Returned once; the server keeps only its hash,
    so a lost token is replaced, never recovered.
    """

    token: str
    created_at: str


class SetModeIn(BaseModel):
    """
    Put a robot into a mode, or take it out of one.

    A statement of intent, not a command: the agent acts on it at its next sync,
    and keeps acting on it afterwards. Setting `nav` on a robot with no map
    assigned is accepted — the agent stays idle and says why, which is more
    useful than refusing a thing the operator will want as soon as they assign
    the map.
    """

    model_config = ConfigDict(extra="forbid")

    desired_mode: DesiredMode
