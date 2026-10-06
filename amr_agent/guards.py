"""
Input guards for the robot agent. Pure Python, no ROS imports, so they are
unit-tested without a ROS install.

Everything arriving over rosbridge or /robot_mode is untrusted: the web UI's
speed presets and file pickers are conveniences, not a security boundary.
"""

from __future__ import annotations

import math
import os
from typing import NamedTuple


class SanitizedTwist(NamedTuple):
    """Six floats in Twist order, plus what was done to get them."""

    linear_x: float
    linear_y: float
    linear_z: float
    angular_x: float
    angular_y: float
    angular_z: float
    rejected: bool  # a component was NaN/Inf: the command was replaced by a stop
    clamped: bool  # linear.x or angular.z was above the limit and cut down


def validate_limit(name: str, value: float) -> float:
    """A speed limit must be a finite number above zero; else ValueError."""
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a number, got {value!r}") from error
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be a finite number > 0, got {value!r}")
    return number


def sanitize_twist(
    lx: float,
    ly: float,
    lz: float,
    ax: float,
    ay: float,
    az: float,
    max_linear: float,
    max_angular: float,
) -> SanitizedTwist:
    """
    Make a teleop command safe for a differential-drive base.

    Any non-finite component turns the whole command into a stop (all zeros,
    rejected=True). Otherwise linear.x and angular.z are clamped to the limits
    and every other axis is zeroed, since the base cannot use them.
    """
    max_linear = validate_limit("max_linear", max_linear)
    max_angular = validate_limit("max_angular", max_angular)

    try:
        values = [float(v) for v in (lx, ly, lz, ax, ay, az)]
    except (TypeError, ValueError):
        return SanitizedTwist(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, True, False)
    if not all(math.isfinite(v) for v in values):
        return SanitizedTwist(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, True, False)

    linear = max(-max_linear, min(max_linear, values[0]))
    angular = max(-max_angular, min(max_angular, values[5]))
    clamped = linear != values[0] or angular != values[5]
    # + 0.0 turns -0.0 into 0.0.
    return SanitizedTwist(linear + 0.0, 0.0, 0.0, 0.0, 0.0, angular + 0.0, False, clamped)


def resolve_map_path(candidate: str, allowed_roots: list[str]) -> str | None:
    """
    The real path of a map yaml inside one of the allowed directories, or None.

    Symlinks are resolved before the check, so neither '..' nor a link inside
    an allowed directory can reach a file outside it. The containment test is
    on path components (commonpath), so '/cache-evil' is not inside '/cache'.
    """
    if not isinstance(candidate, str) or not candidate or "\0" in candidate:
        return None
    try:
        real = os.path.realpath(candidate)
    except (OSError, ValueError):
        return None
    if not real.lower().endswith(".yaml"):
        return None
    if not os.path.isfile(real):
        return None
    for root in allowed_roots:
        if not root:
            continue
        try:
            real_root = os.path.realpath(root)
            if os.path.commonpath([real, real_root]) == real_root:
                return real
        except (OSError, ValueError):
            continue
    return None
