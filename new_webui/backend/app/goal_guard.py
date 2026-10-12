"""
Goals the relay refuses because they lie inside a keep-out zone.

A goal sent to a point inside an active keep-out can never be reached: the
robot's planner treats the keep-out as lethal and answers "no valid path".
Nav2 then runs its recoveries against an area that will not move, for minutes,
nudging the robot about, before giving up. The answer is known before the goal
leaves this server, so it is refused here, in words the operator can act on.

The web UI checks the same thing before sending; this is the control, the UI
the convenience (see ros_policy.py). The robot's agent applies the same rule
to mission steps it drives itself.

Kept out of ros_policy on purpose: that module is pure and runs on every frame,
teleop included. This reads the database, and only for a goal.
"""

from __future__ import annotations

import json
import math
import sqlite3

from app.repositories import robots as robots_repo
from app.repositories import zones as zones_repo
from app.ros_policy import GOAL, logical_name


def point_in_polygon(polygon: list, x: float, y: float) -> bool:
    """Even-odd ray cast: the rule the robot's rasteriser and the web UI use."""
    inside = False
    count = len(polygon)
    for i in range(count):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % count]
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


def keepout_at(zones: list, x: float, y: float) -> str | None:
    """The name of the enabled keep-out that (x, y) lies in, or None."""
    for zone in zones:
        if zone["kind"] != "keepout" or not zone["enabled"]:
            continue
        polygon = zone["polygon"]
        if isinstance(polygon, str):
            try:
                polygon = json.loads(polygon)
            except ValueError:
                continue
        if not isinstance(polygon, list) or len(polygon) < 3:
            continue
        try:
            points = [(float(px), float(py)) for px, py in polygon]
        except (TypeError, ValueError):
            continue
        if point_in_polygon(points, x, y):
            return str(zone["name"])
    return None


def _goal_point(frame: dict) -> tuple[float, float] | None:
    try:
        position = frame["msg"]["pose"]["position"]
        x, y = float(position["x"]), float(position["y"])
    except (KeyError, TypeError, ValueError):
        return None
    return (x, y) if math.isfinite(x) and math.isfinite(y) else None


def goal_refusal(
    connection: sqlite3.Connection, robot_id: str, namespace: str, frame: object
) -> str | None:
    """
    Why this frame, a goal for this robot, must not be forwarded; None if it may.

    Only a publish to the goal topic is looked at. A robot with no map assigned
    has no zones to check, and is let through as before.
    """
    if not isinstance(frame, dict) or frame.get("op") != "publish":
        return None
    if logical_name(namespace, frame.get("topic")) != GOAL:
        return None
    point = _goal_point(frame)
    if point is None:
        return None
    robot = robots_repo.get_robot(connection, robot_id)
    if robot is None or not robot["active_map_id"]:
        return None
    rows = zones_repo.list_zones(connection, robot["active_map_id"], kind="keepout")
    name = keepout_at(rows, *point)
    if name is None:
        return None
    return f"goal ({point[0]:.2f}, {point[1]:.2f}) is inside keep-out zone '{name}'"
