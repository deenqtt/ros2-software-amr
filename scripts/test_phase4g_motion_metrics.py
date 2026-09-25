#!/usr/bin/env python3
"""Focused tests for the frame-aware Phase 4G/4J motion metrics."""

from types import SimpleNamespace
import math

from phase4g_motion_metrics import compute_motion_metrics


def pose(x, y, yaw):
    return SimpleNamespace(x=x, y=y, yaw=yaw)


def test_straight_motion_preserves_world_xy_and_body_metrics():
    metrics = compute_motion_metrics(
        pose(2.0, 3.0, 0.0),
        pose(3.0, 3.04, 0.0),
        pose(2.0, 3.0, 0.0),
        pose(2.97, 3.03, 0.0),
    )

    assert metrics.reference_point == "base_footprint/model_origin"
    assert metrics.ground_delta_x_m == 1.0
    assert math.isclose(metrics.ground_delta_y_m, 0.04)
    assert round(metrics.ground_delta_xy_m, 6) == round((1.0**2 + 0.04**2) ** 0.5, 6)
    assert math.isclose(metrics.ground_forward_delta_m, 1.0)
    assert math.isclose(metrics.ground_lateral_delta_m, 0.04)
    assert round(metrics.odom_forward_delta_m, 6) == 0.97
    assert round(metrics.odom_lateral_delta_m, 6) == 0.03
    assert round(metrics.translational_error_percent, 6) == round(
        100.0 * ((0.03**2 + 0.01**2) ** 0.5) / metrics.ground_delta_xy_m, 6
    )


def test_yaw_error_is_wrapped_and_origin_arc_is_explicit():
    metrics = compute_motion_metrics(
        pose(0.0, 0.0, 3.13),
        pose(0.02, 0.03, -3.13),
        pose(0.0, 0.0, 3.13),
        pose(0.0, 0.0, -3.14),
    )

    assert round(metrics.ground_delta_yaw_deg, 3) == round(0.023185307179586 * 180.0 / 3.141592653589793, 3)
    assert round(metrics.odom_delta_yaw_deg, 3) == round(0.013185307179586 * 180.0 / 3.141592653589793, 3)
    assert metrics.rotational_error_deg < 1.0
    assert round(metrics.ground_origin_arc_m, 6) == round(metrics.ground_delta_xy_m, 6)
    assert metrics.raw_world_xy_note == "preserved; origin arc reported separately"


if __name__ == "__main__":
    test_straight_motion_preserves_world_xy_and_body_metrics()
    test_yaw_error_is_wrapped_and_origin_arc_is_explicit()
    print("phase4g motion metric tests passed")
