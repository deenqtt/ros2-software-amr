import math

from phase4o_metrics import aggregate_value, build_response_curve, evaluate_acceptance


def _trace(kind, command, *, yaw_error=0.0, translation_error_percent=0.0, d2=0.0):
    if kind == "turn":
        ground_yaw = math.radians(90.0 if command["angular_z"] > 0 else -90.0)
        odom_yaw = ground_yaw - math.copysign(math.radians(yaw_error), ground_yaw)
        stop = None
    else:
        ground_yaw = 0.0
        odom_yaw = 0.0
        odom_x = 1.0 - translation_error_percent / 100.0
        stop = {"D1_m": 0.02, "D2_m": d2, "D3_m": 0.0, "D_total_m": 0.02 + d2}
    end = {
        "simulation_time_s": 1.0,
        "ground": {"x": 1.0 if kind == "stop" else 0.0, "y": 0.0, "yaw": ground_yaw},
        "odom": {"x": odom_x if kind == "stop" else 0.0, "y": 0.0, "yaw": odom_yaw},
    }
    return {
        "kind": kind,
        "command": command,
        "samples": [
            {"simulation_time_s": 0.0, "ground": {"x": 0.0, "y": 0.0, "yaw": 0.0}, "odom": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
            end,
        ],
        "event_markers": {"T0": 0.0, "T2": 1.0},
        "stop_distances": stop,
    }


def test_build_response_curve_orders_slip_values_numerically():
    groups = {0.02: [], 0.0: [], 0.035: [], 0.01: []}
    rows = build_response_curve(groups)
    assert [row["slip1"] for row in rows] == [0.0, 0.01, 0.02, 0.035]


def test_aggregate_value_computes_mean_and_worst_per_direction():
    traces = [
        _trace("turn", {"linear_x": 0.0, "angular_z": 0.4}, yaw_error=1.0),
        _trace("turn", {"linear_x": 0.0, "angular_z": 0.4}, yaw_error=3.0),
        _trace("turn", {"linear_x": 0.0, "angular_z": -0.4}, yaw_error=2.0),
        _trace("stop", {"linear_x": 0.2, "angular_z": 0.0}, translation_error_percent=1.0, d2=0.005),
        _trace("stop", {"linear_x": -0.2, "angular_z": 0.0}, translation_error_percent=2.0, d2=0.006),
    ]
    row = aggregate_value(traces, 0.01, symmetry_metrics={"max_yaw_symmetry_error_deg": 1.0}, wheel_tracking=True, stability=True)
    assert math.isclose(row["ccw_mean_error_deg"], 2.0)
    assert math.isclose(row["ccw_worst_error_deg"], 3.0)
    assert math.isclose(row["cw_mean_error_deg"], 2.0)
    assert math.isclose(row["forward_worst_translation_error_percent"], 1.0)
    assert math.isclose(row["reverse_worst_translation_error_percent"], 2.0)
    assert math.isclose(row["forward_D2_m"], 0.005)
    assert math.isclose(row["reverse_D2_m"], 0.006)


def test_acceptance_requires_every_gate():
    passing = {
        "ccw_worst_error_deg": 4.0,
        "cw_worst_error_deg": 4.0,
        "forward_worst_translation_error_percent": 4.0,
        "reverse_worst_translation_error_percent": 4.0,
        "forward_D2_m": 0.009,
        "reverse_D2_m": 0.009,
        "max_yaw_symmetry_error_deg": 2.0,
        "wheel_tracking": True,
        "stability": True,
    }
    result = evaluate_acceptance(passing)
    assert result["overall"] == "PASS"

    failing = dict(passing, reverse_D2_m=0.011)
    assert evaluate_acceptance(failing)["overall"] == "FAIL"
