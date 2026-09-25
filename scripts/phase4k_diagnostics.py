#!/usr/bin/env python3
"""Pure helpers for Phase 4K diagnostic measurements."""

from __future__ import annotations

import math
import json
import re


FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def expected_wheel_omega(
    linear_x: float, angular_z: float, wheel_separation: float, wheel_radius: float
) -> dict[str, float]:
    """Return expected left/right wheel angular speeds for body velocity."""
    left_linear = linear_x - angular_z * wheel_separation / 2.0
    right_linear = linear_x + angular_z * wheel_separation / 2.0
    return {"left": left_linear / wheel_radius, "right": right_linear / wheel_radius}


def expected_pure_turn_wheel_omega(
    angular_z: float, wheel_separation: float, wheel_radius: float
) -> dict[str, float]:
    """Return expected left/right wheel angular speeds for a pure turn."""
    return expected_wheel_omega(0.0, angular_z, wheel_separation, wheel_radius)


def simulation_window_deadline(start_simulation_s: float, offset_s: float) -> float:
    """Return a measurement deadline in simulator time, not wall time."""
    return start_simulation_s + offset_s


def parse_joint_state_block(block: str) -> dict:
    """Parse one text-format ``gz.msgs.Model`` joint-state message."""
    stamp = re.search(
        rf"header\s*\{{.*?sec:\s*({FLOAT}).*?nsec:\s*({FLOAT})",
        block,
        flags=re.DOTALL,
    )
    if stamp is None:
        raise ValueError("joint-state block has no header timestamp")

    joints: dict[str, dict[str, float]] = {}
    for name in ("wheel_left_joint", "wheel_right_joint"):
        match = re.search(
            rf'name:\s*"{re.escape(name)}".*?axis1\s*\{{.*?'
            rf"position:\s*({FLOAT}).*?velocity:\s*({FLOAT})",
            block,
            flags=re.DOTALL,
        )
        if match is not None:
            joints[name] = {
                "position": float(match.group(1)),
                "velocity": float(match.group(2)),
            }
    if set(joints) != {"wheel_left_joint", "wheel_right_joint"}:
        raise ValueError("joint-state block is missing one or both drive joints")
    return {
        "stamp_s": float(stamp.group(1)) + float(stamp.group(2)) * 1e-9,
        "joints": joints,
    }


def parse_dynamic_pose_block(block: str, model_name: str) -> dict[str, float]:
    """Parse one named model pose from a ``gz.msgs.Pose_V`` text message."""
    stamp = re.search(
        rf"header\s*\{{.*?sec:\s*({FLOAT}).*?nsec:\s*({FLOAT})",
        block,
        flags=re.DOTALL,
    )
    if stamp is None:
        raise ValueError("dynamic-pose block has no header timestamp")
    pose = re.search(
        rf'pose\s*\{{\s*name:\s*"{re.escape(model_name)}"(?P<body>.*?)(?=\npose\s*\{{|\Z)',
        block,
        flags=re.DOTALL,
    )
    if pose is None:
        raise ValueError(f"pose block has no model named {model_name}")
    body = pose.group("body")
    position = re.search(rf"position\s*\{{(?P<body>.*?)\}}", body, flags=re.DOTALL)
    orientation = re.search(rf"orientation\s*\{{(?P<body>.*?)\}}", body, flags=re.DOTALL)
    if position is None or orientation is None:
        raise ValueError(f"pose block for {model_name} is incomplete")

    def value(field: str, text: str) -> float:
        match = re.search(rf"\b{field}:\s*({FLOAT})", text)
        return float(match.group(1)) if match else 0.0

    x = value("x", position.group("body"))
    y = value("y", position.group("body"))
    z = value("z", position.group("body"))
    qx = value("x", orientation.group("body"))
    qy = value("y", orientation.group("body"))
    qz = value("z", orientation.group("body"))
    qw = value("w", orientation.group("body"))
    roll = math.atan2(2 * (qw * qx + qy * qz), 1 - 2 * (qx * qx + qy * qy))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (qw * qy - qz * qx))))
    yaw = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
    return {
        "stamp_s": float(stamp.group(1)) + float(stamp.group(2)) * 1e-9,
        "x": x,
        "y": y,
        "z": z,
        "roll": roll,
        "pitch": pitch,
        "yaw": yaw,
    }


def parse_dynamic_pose_json_line(line: str, model_name: str) -> dict[str, float]:
    """Parse one JSON-formatted ``gz.msgs.Pose_V`` message."""
    message = json.loads(line)
    stamp = message.get("header", {}).get("stamp", {})
    poses = message.get("pose", [])
    pose = next((item for item in poses if item.get("name") == model_name), None)
    if pose is None:
        raise ValueError(f"JSON pose message has no model named {model_name}")

    position = pose.get("position", {})
    orientation = pose.get("orientation", {})
    x = float(position.get("x", 0.0))
    y = float(position.get("y", 0.0))
    z = float(position.get("z", 0.0))
    qx = float(orientation.get("x", 0.0))
    qy = float(orientation.get("y", 0.0))
    qz = float(orientation.get("z", 0.0))
    qw = float(orientation.get("w", 1.0))
    roll = math.atan2(2 * (qw * qx + qy * qz), 1 - 2 * (qx * qx + qy * qy))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (qw * qy - qz * qx))))
    yaw = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
    return {
        "stamp_s": float(stamp.get("sec", 0.0)) + float(stamp.get("nsec", 0.0)) * 1e-9,
        "x": x,
        "y": y,
        "z": z,
        "roll": roll,
        "pitch": pitch,
        "yaw": yaw,
    }
