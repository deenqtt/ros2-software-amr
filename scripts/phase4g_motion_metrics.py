#!/usr/bin/env python3
"""Pure frame-aware metrics shared by the Phase 4G/4J motion probe."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MotionMetrics:
    reference_point: str
    raw_world_xy_note: str
    ground_delta_x_m: float
    ground_delta_y_m: float
    odom_delta_x_m: float
    odom_delta_y_m: float
    ground_delta_xy_m: float
    odom_delta_xy_m: float
    translational_error_m: float
    translational_error_percent: float
    ground_forward_delta_m: float
    ground_lateral_delta_m: float
    odom_forward_delta_m: float
    odom_lateral_delta_m: float
    ground_delta_yaw_deg: float
    odom_delta_yaw_deg: float
    rotational_error_deg: float
    ground_origin_arc_m: float


def wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))


def _body_frame_delta(dx: float, dy: float, heading: float) -> tuple[float, float]:
    forward = dx * math.cos(heading) + dy * math.sin(heading)
    lateral = -dx * math.sin(heading) + dy * math.cos(heading)
    return forward, lateral


def compute_motion_metrics(
    ground_start,
    ground_final,
    odom_start,
    odom_final,
    reference_point: str = "base_footprint/model_origin",
) -> MotionMetrics:
    """Compare independent Gazebo and ROS poses in a common initial body frame.

    The Gazebo model-origin XY displacement remains raw and is also reported as
    ``ground_origin_arc_m``. This makes the small caster-induced origin arc
    visible without treating it as a hidden odometry correction.
    """
    ground_dx = ground_final.x - ground_start.x
    ground_dy = ground_final.y - ground_start.y
    odom_dx = odom_final.x - odom_start.x
    odom_dy = odom_final.y - odom_start.y
    ground_distance = math.hypot(ground_dx, ground_dy)
    odom_distance = math.hypot(odom_dx, odom_dy)
    vector_error = math.hypot(ground_dx - odom_dx, ground_dy - odom_dy)
    denominator = max(ground_distance, odom_distance, 1e-6)
    ground_forward, ground_lateral = _body_frame_delta(
        ground_dx, ground_dy, ground_start.yaw
    )
    odom_forward, odom_lateral = _body_frame_delta(
        odom_dx, odom_dy, ground_start.yaw
    )
    ground_yaw = math.degrees(wrap_angle(ground_final.yaw - ground_start.yaw))
    odom_yaw = math.degrees(wrap_angle(odom_final.yaw - odom_start.yaw))
    yaw_error = abs(math.degrees(wrap_angle(math.radians(ground_yaw - odom_yaw))))
    return MotionMetrics(
        reference_point=reference_point,
        raw_world_xy_note="preserved; origin arc reported separately",
        ground_delta_x_m=ground_dx,
        ground_delta_y_m=ground_dy,
        odom_delta_x_m=odom_dx,
        odom_delta_y_m=odom_dy,
        ground_delta_xy_m=ground_distance,
        odom_delta_xy_m=odom_distance,
        translational_error_m=vector_error,
        translational_error_percent=100.0 * vector_error / denominator,
        ground_forward_delta_m=ground_forward,
        ground_lateral_delta_m=ground_lateral,
        odom_forward_delta_m=odom_forward,
        odom_lateral_delta_m=odom_lateral,
        ground_delta_yaw_deg=ground_yaw,
        odom_delta_yaw_deg=odom_yaw,
        rotational_error_deg=yaw_error,
        ground_origin_arc_m=ground_distance,
    )
