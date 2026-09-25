import math

from phase4n_metrics import aggregate_stop, aggregate_turn, trace_metrics


def _trace(kind, ground_yaw, odom_yaw, stop=None):
    samples = [
        {
            "simulation_time_s": 0.0,
            "ground": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            "odom": {"x": 0.0, "y": 0.0, "yaw": 0.0},
        },
        {
            "simulation_time_s": 1.0,
            "ground": {"x": 1.0, "y": 0.0, "yaw": ground_yaw},
            "odom": {"x": 0.9, "y": 0.0, "yaw": odom_yaw},
        },
    ]
    result = {
        "kind": kind,
        "samples": samples,
        "event_markers": {"T0": 0.0, "T2": 1.0},
        "stop_distances": stop,
    }
    return result


def test_trace_metrics_aligns_turn_yaw_to_initial_pose():
    result = trace_metrics(_trace("turn", math.radians(90), math.radians(80)))
    assert math.isclose(result["physical_yaw_deg"], 90.0)
    assert math.isclose(result["odom_yaw_deg"], 80.0)
    assert math.isclose(result["yaw_error_deg"], 10.0)
    assert math.isclose(result["yaw_ratio"], 90.0 / 80.0)


def test_aggregate_stop_returns_mean_and_worst_case():
    traces = [
        _trace("stop", 0.0, 0.0, {"D1_m": 0.01, "D2_m": 0.02, "D3_m": 0.03, "D_total_m": 0.06}),
        _trace("stop", 0.0, 0.0, {"D1_m": 0.02, "D2_m": 0.01, "D3_m": 0.01, "D_total_m": 0.04}),
    ]
    result = aggregate_stop(traces)
    assert math.isclose(result["mean_D_total_m"], 0.05)
    assert math.isclose(result["worst_D_total_m"], 0.06)


def test_aggregate_turn_returns_mean_and_worst_error():
    traces = [
        _trace("turn", math.radians(90), math.radians(80)),
        _trace("turn", math.radians(90), math.radians(85)),
    ]
    result = aggregate_turn(traces)
    assert math.isclose(result["mean_yaw_error_deg"], 7.5)
    assert math.isclose(result["worst_yaw_error_deg"], 10.0)
