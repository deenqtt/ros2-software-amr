#!/usr/bin/env python3
"""Pure metrics for Phase 4N slip-causality traces.

The trace's dynamic-pose topic is the independent physical reference.  ROS
odometry is compared to that reference only after both poses are aligned to
the first recorded sample; no odometry value is used as ground truth.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))


def _sample_near(samples: list[dict], timestamp: float) -> dict:
    return min(samples, key=lambda sample: abs(float(sample["simulation_time_s"]) - timestamp))


def _pose(sample: dict, key: str) -> dict:
    return sample.get(key) or {}


def _delta_xy(start: dict, end: dict, key: str) -> tuple[float, float]:
    first = _pose(start, key)
    last = _pose(end, key)
    return (
        float(last.get("x", 0.0)) - float(first.get("x", 0.0)),
        float(last.get("y", 0.0)) - float(first.get("y", 0.0)),
    )


def _translation_metrics(start: dict, end: dict) -> dict[str, float]:
    ground_dx, ground_dy = _delta_xy(start, end, "ground")
    odom_dx, odom_dy = _delta_xy(start, end, "odom")
    ground_distance = math.hypot(ground_dx, ground_dy)
    odom_distance = math.hypot(odom_dx, odom_dy)
    error_m = math.hypot(ground_dx - odom_dx, ground_dy - odom_dy)
    denominator = max(ground_distance, odom_distance, 1e-9)
    return {
        "ground_displacement_m": ground_distance,
        "odom_displacement_m": odom_distance,
        "translation_error_m": error_m,
        "translation_error_percent": 100.0 * error_m / denominator,
    }


def trace_metrics(trace: dict) -> dict:
    samples = trace.get("samples") or []
    if not samples:
        raise ValueError("trace has no samples")
    markers = trace.get("event_markers") or {}
    end_time = markers.get("T2") or float(samples[-1]["simulation_time_s"])
    start = samples[0]
    end = _sample_near(samples, float(end_time))
    result = {
        "kind": trace.get("kind"),
        "model": trace.get("model"),
        "sample_count": len(samples),
        "ground_pose_age_max_s": trace.get("ground_pose_age_max_s"),
        **_translation_metrics(start, end),
    }

    ground_start_yaw = float(_pose(start, "ground").get("yaw", 0.0))
    ground_end_yaw = float(_pose(end, "ground").get("yaw", 0.0))
    odom_start_yaw = float(_pose(start, "odom").get("yaw", 0.0))
    odom_end_yaw = float(_pose(end, "odom").get("yaw", 0.0))
    ground_yaw_signed = math.degrees(wrap_angle(ground_end_yaw - ground_start_yaw))
    odom_yaw_signed = math.degrees(wrap_angle(odom_end_yaw - odom_start_yaw))
    yaw_error = abs(math.degrees(wrap_angle(math.radians(ground_yaw_signed - odom_yaw_signed))))
    result.update(
        {
            "physical_yaw_deg": abs(ground_yaw_signed),
            "odom_yaw_deg": abs(odom_yaw_signed),
            "ground_yaw_signed_deg": ground_yaw_signed,
            "odom_yaw_signed_deg": odom_yaw_signed,
            "yaw_error_deg": yaw_error,
            "yaw_ratio": (
                abs(ground_yaw_signed) / abs(odom_yaw_signed)
                if abs(odom_yaw_signed) > 1e-9
                else None
            ),
        }
    )
    stop = trace.get("stop_distances") or {}
    for key in ("D1_m", "D2_m", "D3_m", "D_total_m"):
        result[key] = stop.get(key)
    return result


def _mean(values: list[float | None]) -> float | None:
    usable = [float(value) for value in values if value is not None]
    return sum(usable) / len(usable) if usable else None


def _worst(values: list[float | None]) -> float | None:
    usable = [float(value) for value in values if value is not None]
    return max(usable) if usable else None


def aggregate_turn(traces: list[dict]) -> dict:
    metrics = [trace_metrics(trace) for trace in traces]
    return {
        "repeat_count": len(metrics),
        "mean_yaw_error_deg": _mean([item["yaw_error_deg"] for item in metrics]),
        "worst_yaw_error_deg": _worst([item["yaw_error_deg"] for item in metrics]),
        "mean_yaw_ratio": _mean([item["yaw_ratio"] for item in metrics]),
        "worst_translation_error_percent": _worst(
            [item["translation_error_percent"] for item in metrics]
        ),
        "traces": metrics,
    }


def aggregate_stop(traces: list[dict]) -> dict:
    metrics = [trace_metrics(trace) for trace in traces]
    return {
        "repeat_count": len(metrics),
        "mean_D1_m": _mean([item["D1_m"] for item in metrics]),
        "mean_D2_m": _mean([item["D2_m"] for item in metrics]),
        "mean_D3_m": _mean([item["D3_m"] for item in metrics]),
        "mean_D_total_m": _mean([item["D_total_m"] for item in metrics]),
        "worst_D_total_m": _worst([item["D_total_m"] for item in metrics]),
        "mean_translation_error_percent": _mean(
            [item["translation_error_percent"] for item in metrics]
        ),
        "worst_translation_error_percent": _worst(
            [item["translation_error_percent"] for item in metrics]
        ),
        "traces": metrics,
    }


def load_traces(paths: list[Path]) -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("turn", "stop"), required=True)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    traces = load_traces(args.paths)
    result = aggregate_turn(traces) if args.kind == "turn" else aggregate_stop(traces)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
