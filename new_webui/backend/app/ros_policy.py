"""
What a signed-in person may say to a robot's rosbridge.

The browser no longer talks to rosbridge itself: it talks to the backend, which
relays to the robot (see api/ros_proxy.py). Every frame the browser sends passes
through ``decide`` first. rosbridge has no notion of who is calling, so this is
the only place a viewer is told no; the buttons the UI greys out are a
convenience, not the control.

The rule is an allow-list. A frame is forwarded only if it is one of the few
things the web UI actually does — read status topics, drive by teleop, send a
goal or an initial pose, stop, switch to mapping, save a map — and only for a
role that may. Anything else (raw /cmd_vel, action goals, other services,
advertising a service, changing rosbridge's log level, fragments, CBOR) is
refused, whatever the role.

Pure and cheap: no I/O, a dictionary lookup or two per frame. Teleop arrives at
10 Hz per open joystick and must not cost a database query.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.auth import ROLES

_RANK: dict[str, int] = {role: rank for rank, role in enumerate(ROLES)}

# Names the frontend never namespaces (see frontend/src/domain/ros/topics.ts).
_GLOBAL = frozenset({"/tf", "/tf_static", "/rosout"})

#: Topics any signed-in person may read.
SUBSCRIBABLE = frozenset(
    {
        "/robot_status",
        "/battery_state",
        "/dock_status",
        "/robot_mode_status",
        "/tf",
        "/tf_static",
        "/odom",
        "/scan",
        "/map",
        "/global_costmap/costmap",
        "/plan",
        "/rosout",
        "/navigate_to_pose/_action/status",
        "/particle_cloud",
        "/robot_description",
    }
)

TELEOP = "/teleop/cmd_vel"
GOAL = "/goal_pose"
INITIAL_POSE = "/initialpose"
CANCEL_GOAL = "/navigate_to_pose/_action/cancel_goal"
ROBOT_MODE = "/robot_mode"
MAP_SAVE = "/map_save"

#: Topic -> (message type it must be advertised with, least role to advertise).
#  Teleop is open to viewers on purpose: the drive screen streams zero twists
#  whoever is watching, and a zero twist is a stop.
_ADVERTISABLE = {
    TELEOP: ("geometry_msgs/msg/Twist", "viewer"),
    GOAL: ("geometry_msgs/msg/PoseStamped", "operator"),
    INITIAL_POSE: ("geometry_msgs/msg/PoseWithCovarianceStamped", "operator"),
}

_SERVICES = frozenset({CANCEL_GOAL, ROBOT_MODE, MAP_SAVE})

_TOPIC_NAMES = SUBSCRIBABLE | set(_ADVERTISABLE)

_SUBSCRIBE_FIELDS = frozenset(
    {"op", "id", "topic", "type", "throttle_rate", "queue_length", "compression", "qos"}
)
_ADVERTISE_FIELDS = frozenset({"op", "id", "topic", "type", "latch", "queue_size"})
_PUBLISH_FIELDS = frozenset({"op", "id", "topic", "msg", "latch"})
_CALL_FIELDS = frozenset({"op", "id", "service", "type", "args"})
_COMPRESSIONS = frozenset({"none", "png"})

# Matched with fullmatch: `$` would also accept a trailing newline.
MAP_NAME = re.compile(r"[A-Za-z0-9 _.-]{1,64}")
#: Largest magnitude accepted for an integer field. ROS integers are at most 64
#: bits, and a 400-digit integer must not reach float() or math.isfinite().
_INT_LIMIT = 2**64


def map_name_ok(name: object) -> bool:
    """A map name the agent can use as a file name without surprises."""
    return (
        isinstance(name, str)
        and MAP_NAME.fullmatch(name) is not None
        and ".." not in name
        and not name.startswith(".")
        and name.strip() != ""
    )


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str
    #: Worth a row in the audit trail (a command, not a stream of telemetry).
    audit: bool = False


def _allow(reason: str = "ok", *, audit: bool = False) -> Decision:
    return Decision(True, reason, audit)


def _deny(reason: str, *, audit: bool = False) -> Decision:
    return Decision(False, reason, audit)


def _at_least(role: str, minimum: str) -> bool:
    rank = _RANK.get(role)
    return rank is not None and rank >= _RANK[minimum]


def ros_name(namespace: str, name: str) -> str:
    """The frontend's ``join``: ``/ns`` + name, except for the global names."""
    ns = namespace.strip("/")
    if not ns or name in _GLOBAL:
        return name
    return f"/{ns}{name}"


@lru_cache(maxsize=256)
def _resolver(namespace: str) -> dict[str, str]:
    """Full ROS name under this namespace -> the logical name the rules use."""
    return {ros_name(namespace, name): name for name in _TOPIC_NAMES | _SERVICES}


def logical_name(namespace: str, name: object) -> str | None:
    if not isinstance(name, str):
        return None
    return _resolver(namespace or "").get(name)


def _number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return -_INT_LIMIT < value < _INT_LIMIT
    return isinstance(value, float)


def _all_finite(value: Any, depth: int = 0) -> bool:
    """No NaN or infinity anywhere in a message (they reach a controller as-is)."""
    if depth > 16:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return -_INT_LIMIT < value < _INT_LIMIT
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_all_finite(item, depth + 1) for item in value.values())
    if isinstance(value, list):
        return all(_all_finite(item, depth + 1) for item in value)
    return True


def _twist_components(msg: object) -> list[float] | None:
    """The six numbers of a Twist, or None if the message is not one."""
    if not isinstance(msg, dict) or not set(msg) <= {"linear", "angular"}:
        return None
    values: list[float] = []
    for part in ("linear", "angular"):
        vector = msg.get(part, {})
        if not isinstance(vector, dict) or not set(vector) <= {"x", "y", "z"}:
            return None
        for axis in ("x", "y", "z"):
            component = vector.get(axis, 0)
            if not _number(component):
                return None
            values.append(float(component))
    return values


def _counts_ok(frame: dict, fields: tuple[str, ...]) -> bool:
    """Rates and queue sizes: small non-negative integers, when present."""
    for field in fields:
        value = frame.get(field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**31:
            return False
    return True


def _subscribe(frame: dict, topic: str | None) -> Decision:
    if not set(frame) <= _SUBSCRIBE_FIELDS:
        return _deny("unexpected fields in subscribe")
    if not _counts_ok(frame, ("throttle_rate", "queue_length")) or not _all_finite(
        frame.get("qos")
    ):
        return _deny("malformed subscribe")
    compression = frame.get("compression", "none")
    if compression is not None and compression not in _COMPRESSIONS:
        return _deny(f"compression {compression!r} is not allowed")
    if topic not in SUBSCRIBABLE:
        return _deny(f"topic {frame.get('topic')!r} may not be subscribed")
    return _allow()


def _advertise(frame: dict, topic: str | None, role: str) -> Decision:
    if not set(frame) <= _ADVERTISE_FIELDS:
        return _deny("unexpected fields in advertise")
    if not _counts_ok(frame, ("queue_size",)):
        return _deny("malformed advertise")
    rule = _ADVERTISABLE.get(topic or "")
    if rule is None:
        return _deny(f"topic {frame.get('topic')!r} may not be published")
    message_type, minimum = rule
    if frame.get("type") != message_type:
        return _deny(f"{topic} must be advertised as {message_type}")
    if frame.get("latch"):
        return _deny("latched publishing is not allowed")
    if not _at_least(role, minimum):
        return _deny(f"publishing {topic} needs the {minimum} role")
    return _allow()


def _publish(frame: dict, topic: str | None, role: str) -> Decision:
    if not set(frame) <= _PUBLISH_FIELDS:
        return _deny("unexpected fields in publish")
    if frame.get("latch"):
        return _deny("latched publishing is not allowed")
    msg = frame.get("msg")
    if topic == TELEOP:
        components = _twist_components(msg)
        if components is None:
            return _deny("teleop message is not a Twist")
        if not all(math.isfinite(value) for value in components):
            return _deny("teleop message has a non-finite number")
        if all(value == 0 for value in components):
            # A stop. Anyone watching may send one.
            return _allow()
        if not _at_least(role, "operator"):
            return _deny("driving needs the operator role")
        return _allow()
    if topic in (GOAL, INITIAL_POSE):
        if not isinstance(msg, dict) or not _all_finite(msg):
            return _deny(f"{topic} message is malformed", audit=True)
        if not _at_least(role, "operator"):
            return _deny(f"publishing {topic} needs the operator role", audit=True)
        return _allow(audit=True)
    return _deny(f"topic {frame.get('topic')!r} may not be published")


def _call_service(frame: dict, service: str | None, role: str) -> Decision:
    if not set(frame) <= _CALL_FIELDS:
        return _deny("unexpected fields in call_service", audit=True)
    args = frame.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict) or not _all_finite(args):
        return _deny("service arguments are malformed", audit=True)

    if service == CANCEL_GOAL:
        # Stop-class: anyone watching may stop the robot.
        return _allow(audit=True)
    if service == ROBOT_MODE:
        if set(args) != {"robot_mode"}:
            return _deny("robot_mode takes exactly one argument, robot_mode", audit=True)
        mode = args["robot_mode"]
        if mode == "stop":
            return _allow(audit=True)
        if mode == "map":
            if not _at_least(role, "operator"):
                return _deny("switching to mapping needs the operator role", audit=True)
            return _allow(audit=True)
        return _deny("only 'stop' and 'map' may be requested from the browser", audit=True)
    if service == MAP_SAVE:
        if set(args) != {"robot_mode"}:
            return _deny("map_save takes exactly one argument, robot_mode", audit=True)
        name = args["robot_mode"]
        if not map_name_ok(name):
            return _deny(
                "map name must be 1-64 letters, digits, spaces, . _ or -, without '..'",
                audit=True,
            )
        if not _at_least(role, "operator"):
            return _deny("saving a map needs the operator role", audit=True)
        return _allow(audit=True)
    return _deny(f"service {frame.get('service')!r} may not be called", audit=True)


def decide(frame: dict, role: str, namespace: str) -> Decision:
    """
    Whether this rosbridge v2 frame from a browser may reach the robot.

    ``role`` is the caller's current role; ``namespace`` the robot's, as stored
    in the registry. Never raises on malformed input: a frame that does not
    parse into something recognisable is denied. An exception here would end
    the relay, so anything a hostile number or shape can provoke is a refusal.
    """
    try:
        return _decide(frame, role, namespace)
    except (OverflowError, ValueError, TypeError, RecursionError):
        return _deny("malformed message")


def _decide(frame: dict, role: str, namespace: str) -> Decision:
    if not isinstance(frame, dict):
        return _deny("not a rosbridge message")
    op = frame.get("op")
    if op == "unsubscribe":
        return _allow()
    if op == "unadvertise":
        return _allow()
    if op == "subscribe":
        return _subscribe(frame, logical_name(namespace, frame.get("topic")))
    if op == "advertise":
        return _advertise(frame, logical_name(namespace, frame.get("topic")), role)
    if op == "publish":
        return _publish(frame, logical_name(namespace, frame.get("topic")), role)
    if op == "call_service":
        return _call_service(frame, logical_name(namespace, frame.get("service")), role)
    if op in ("send_action_goal", "cancel_action_goal"):
        return _deny(f"{op} is not allowed", audit=True)
    if isinstance(op, str):
        return _deny(f"op {op[:40]!r} is not allowed")
    return _deny("not a rosbridge message")
