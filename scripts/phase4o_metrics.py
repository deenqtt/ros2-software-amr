#!/usr/bin/env python3
"""Aggregate the controlled Phase 4O slip1 response curve."""

from __future__ import annotations

import math

from phase4n_metrics import trace_metrics


def _mean(values):
    values = [float(value) for value in values if value is not None]
    return sum(values) / len(values) if values else None


def _worst(values):
    values = [float(value) for value in values if value is not None]
    return max(values) if values else None


def _select(metrics, command_key, predicate):
    return [item for item in metrics if predicate(float((item["command"] or {}).get(command_key, 0.0)))]


def _command(trace):
    return trace.get("command") or {}


def _trace_settle_intervals(trace):
    markers = trace.get("event_markers") or {}
    t2, t3, t4 = markers.get("T2"), markers.get("T3"), markers.get("T4")
    return (
        float(t3) - float(t2) if t2 is not None and t3 is not None else None,
        float(t4) - float(t3) if t3 is not None and t4 is not None else None,
    )


def _straight_drift(trace):
    samples = trace.get("samples") or []
    markers = trace.get("event_markers") or {}
    if not samples or markers.get("T2") is None:
        return None, None
    end = min(samples, key=lambda item: abs(float(item["simulation_time_s"]) - float(markers["T2"])))
    start_ground = samples[0].get("ground") or {}
    end_ground = end.get("ground") or {}
    dx = float(end_ground.get("x", 0.0)) - float(start_ground.get("x", 0.0))
    dy = float(end_ground.get("y", 0.0)) - float(start_ground.get("y", 0.0))
    heading = float(start_ground.get("yaw", 0.0))
    lateral = abs(-dx * math.sin(heading) + dy * math.cos(heading))
    yaw_drift = abs(math.degrees(float(end_ground.get("yaw", 0.0)) - heading))
    return lateral, yaw_drift


def aggregate_value(
    traces: list[dict],
    slip1: float,
    *,
    symmetry_metrics: dict | None = None,
    wheel_tracking: bool | None = None,
    stability: bool | None = None,
) -> dict:
    measured = []
    for trace in traces:
        item = trace_metrics(trace)
        item["command"] = _command(trace)
        item["T2_to_T3_s"], item["T3_to_T4_s"] = _trace_settle_intervals(trace)
        item["lateral_drift_m"], item["yaw_drift_deg"] = _straight_drift(trace)
        measured.append(item)

    ccw = _select(measured, "angular_z", lambda value: value > 0.0)
    cw = _select(measured, "angular_z", lambda value: value < 0.0)
    forward = _select(measured, "linear_x", lambda value: value > 0.0)
    reverse = _select(measured, "linear_x", lambda value: value < 0.0)

    def values(items, key):
        return [item.get(key) for item in items]

    mirror_error = (symmetry_metrics or {}).get("max_yaw_symmetry_error_deg")
    row = {
        "slip1": float(slip1),
        "repeat_count": len(measured),
        "ccw_repeat_count": len(ccw),
        "cw_repeat_count": len(cw),
        "forward_repeat_count": len(forward),
        "reverse_repeat_count": len(reverse),
        "ccw_mean_error_deg": _mean(values(ccw, "yaw_error_deg")),
        "ccw_worst_error_deg": _worst(values(ccw, "yaw_error_deg")),
        "cw_mean_error_deg": _mean(values(cw, "yaw_error_deg")),
        "cw_worst_error_deg": _worst(values(cw, "yaw_error_deg")),
        "ccw_mean_yaw_ratio": _mean(values(ccw, "yaw_ratio")),
        "cw_mean_yaw_ratio": _mean(values(cw, "yaw_ratio")),
        "forward_mean_translation_error_percent": _mean(values(forward, "translation_error_percent")),
        "forward_worst_translation_error_percent": _worst(values(forward, "translation_error_percent")),
        "reverse_mean_translation_error_percent": _mean(values(reverse, "translation_error_percent")),
        "reverse_worst_translation_error_percent": _worst(values(reverse, "translation_error_percent")),
        "forward_D1_m": _mean(values(forward, "D1_m")),
        "forward_D2_m": _mean(values(forward, "D2_m")),
        "forward_D3_m": _mean(values(forward, "D3_m")),
        "reverse_D1_m": _mean(values(reverse, "D1_m")),
        "reverse_D2_m": _mean(values(reverse, "D2_m")),
        "reverse_D3_m": _mean(values(reverse, "D3_m")),
        "forward_T2_to_T3_s": _mean(values(forward, "T2_to_T3_s")),
        "forward_T3_to_T4_s": _mean(values(forward, "T3_to_T4_s")),
        "reverse_T2_to_T3_s": _mean(values(reverse, "T2_to_T3_s")),
        "reverse_T3_to_T4_s": _mean(values(reverse, "T3_to_T4_s")),
        "forward_worst_lateral_drift_m": _worst(values(forward, "lateral_drift_m")),
        "reverse_worst_lateral_drift_m": _worst(values(reverse, "lateral_drift_m")),
        "forward_worst_yaw_drift_deg": _worst(values(forward, "yaw_drift_deg")),
        "reverse_worst_yaw_drift_deg": _worst(values(reverse, "yaw_drift_deg")),
        "max_yaw_symmetry_error_deg": mirror_error,
        "wheel_tracking": wheel_tracking,
        "stability": stability,
        "traces": measured,
    }
    row["acceptance"] = evaluate_acceptance(row)
    return row


def build_response_curve(groups: dict[float, list[dict]]) -> list[dict]:
    rows = []
    for slip1 in sorted(groups):
        if groups[slip1]:
            rows.append(aggregate_value(groups[slip1], float(slip1)))
        else:
            rows.append({"slip1": float(slip1), "acceptance": evaluate_acceptance({})})
    return rows


def _limit(value, threshold):
    if value is None:
        return "NOT TESTED"
    return "PASS" if float(value) <= threshold else "FAIL"


def evaluate_acceptance(row: dict) -> dict[str, str]:
    gates = {
        "turn": "PASS" if row.get("ccw_worst_error_deg") is not None and row.get("cw_worst_error_deg") is not None and row["ccw_worst_error_deg"] <= 5.0 and row["cw_worst_error_deg"] <= 5.0 else ("FAIL" if row.get("ccw_worst_error_deg") is not None or row.get("cw_worst_error_deg") is not None else "NOT TESTED"),
        "straight": "PASS" if row.get("forward_worst_translation_error_percent") is not None and row.get("reverse_worst_translation_error_percent") is not None and row["forward_worst_translation_error_percent"] <= 5.0 and row["reverse_worst_translation_error_percent"] <= 5.0 else ("FAIL" if row.get("forward_worst_translation_error_percent") is not None or row.get("reverse_worst_translation_error_percent") is not None else "NOT TESTED"),
        "D2": "PASS" if row.get("forward_D2_m") is not None and row.get("reverse_D2_m") is not None and row["forward_D2_m"] <= 0.010 and row["reverse_D2_m"] <= 0.010 else ("FAIL" if row.get("forward_D2_m") is not None or row.get("reverse_D2_m") is not None else "NOT TESTED"),
        "symmetry": _limit(row.get("max_yaw_symmetry_error_deg"), 5.0),
        "wheel_tracking": "PASS" if row.get("wheel_tracking") is True else ("FAIL" if row.get("wheel_tracking") is False else "NOT TESTED"),
        "stability": "PASS" if row.get("stability") is True else ("FAIL" if row.get("stability") is False else "NOT TESTED"),
    }
    gates["overall"] = "PASS" if all(value == "PASS" for key, value in gates.items() if key != "overall") else ("FAIL" if "FAIL" in gates.values() else "NOT TESTED")
    return gates
