#!/usr/bin/env python3
"""Unit tests for Phase 4M continuous-trace diagnostics."""

import math

from phase4m_diagnostics import (
    body_speed_from_samples,
    find_event_markers,
    mirror_symmetry_metrics,
    segment_stop_distances,
)


def sample(t, cmd_z, left_v, right_v, x, y, yaw, odom_x=None, odom_y=None, odom_yaw=None):
    return {
        "simulation_time_s": t,
        "command": {"linear_x": 0.0, "angular_z": cmd_z},
        "joints": {
            "wheel_left_joint": {"position": left_v * t, "velocity": left_v},
            "wheel_right_joint": {"position": right_v * t, "velocity": right_v},
        },
        "ground": {"x": x, "y": y, "yaw": yaw, "roll": 0.0, "pitch": 0.0},
        "odom": {
            "x": x if odom_x is None else odom_x,
            "y": y if odom_y is None else odom_y,
            "yaw": yaw if odom_yaw is None else odom_yaw,
        },
    }


def test_body_speed_uses_simulation_time_and_has_zero_idle_speed():
    samples = [sample(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0), sample(0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
    body_speed_from_samples(samples)
    assert samples[1]["derived"]["ground_linear_speed_mps"] == 0.0


def test_event_markers_distinguish_wheel_stop_from_body_stop():
    samples = [
        sample(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        sample(1.0, 0.4, -0.9, 0.9, 0.0, 0.0, 0.0),
        sample(2.0, 0.0, 0.1, 0.1, 0.0, 0.0, 0.2),
        sample(3.0, 0.0, 0.0, 0.0, 0.05, 0.0, 0.2),
        sample(4.0, 0.0, 0.0, 0.0, 0.05, 0.0, 0.2),
        sample(5.0, 0.0, 0.0, 0.0, 0.05, 0.0, 0.2),
    ]
    body_speed_from_samples(samples)
    markers = find_event_markers(samples, wheel_threshold=0.02, body_speed_threshold=0.01, body_settle_window_s=1.0)
    assert markers["T0"] == 1.0
    assert markers["T2"] == 2.0
    assert markers["T3"] == 3.0
    assert markers["T4"] == 4.0


def test_stop_distances_are_partitioned_at_event_times():
    samples = [
        sample(0.0, 0.2, 2.0, 2.0, 0.0, 0.0, 0.0),
        sample(1.0, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0),
        sample(2.0, 0.0, 0.0, 0.0, 0.15, 0.0, 0.0),
        sample(3.0, 0.0, 0.0, 0.0, 0.17, 0.0, 0.0),
    ]
    distances = segment_stop_distances(samples, {"T2": 0.0, "T3": 1.0, "T4": 2.0, "T5": 3.0})
    assert math.isclose(distances["D1_m"], 0.1)
    assert math.isclose(distances["D2_m"], 0.05)
    assert math.isclose(distances["D3_m"], 0.02)
    assert math.isclose(distances["D_total_m"], 0.17)


def test_mirror_metrics_normalize_initial_yaw_and_compare_signs():
    ccw = [sample(0.0, 0.4, -0.9, 0.9, 0.0, 0.0, 0.2), sample(1.0, 0.4, -0.9, 0.9, 0.0, 0.0, 0.6)]
    cw = [sample(0.0, -0.4, 0.9, -0.9, 0.0, 0.0, -0.3), sample(1.0, -0.4, 0.9, -0.9, 0.0, 0.0, -0.7)]
    metrics = mirror_symmetry_metrics(ccw, cw)
    assert metrics["max_yaw_symmetry_error_deg"] < 1e-9
    assert metrics["max_left_velocity_mismatch_rad_s"] < 1e-9
    assert metrics["max_right_velocity_mismatch_rad_s"] < 1e-9


if __name__ == "__main__":
    test_body_speed_uses_simulation_time_and_has_zero_idle_speed()
    test_event_markers_distinguish_wheel_stop_from_body_stop()
    test_stop_distances_are_partitioned_at_event_times()
    test_mirror_metrics_normalize_initial_yaw_and_compare_signs()
    print("phase4m diagnostic tests passed")
