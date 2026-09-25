#!/usr/bin/env python3
"""Pure metrics for Phase 4M continuous Gazebo traces."""

from __future__ import annotations

import math


def wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))


def _ground(sample: dict) -> dict:
    return sample.get("ground") or {}


def _joint(sample: dict, name: str) -> dict:
    data = sample.get("joints") or {}
    if "joints" in data:
        data = data["joints"] or {}
    return (data.get(name) or {})


def _time(sample: dict) -> float:
    return float(sample["simulation_time_s"])


def body_speed_from_samples(samples: list[dict]) -> list[dict]:
    """Annotate samples with finite-difference ground velocity in sim time."""
    previous = None
    for current in samples:
        if previous is None:
            linear_speed = 0.0
            angular_speed = 0.0
        else:
            dt = _time(current) - _time(previous)
            if dt <= 0.0:
                linear_speed = 0.0
                angular_speed = 0.0
            else:
                p0 = _ground(previous)
                p1 = _ground(current)
                linear_speed = math.hypot(
                    float(p1.get("x", 0.0)) - float(p0.get("x", 0.0)),
                    float(p1.get("y", 0.0)) - float(p0.get("y", 0.0)),
                ) / dt
                angular_speed = abs(
                    wrap_angle(float(p1.get("yaw", 0.0)) - float(p0.get("yaw", 0.0)))
                ) / dt
        current.setdefault("derived", {})["ground_linear_speed_mps"] = linear_speed
        current["derived"]["ground_angular_speed_rps"] = angular_speed
        previous = current
    return samples


def _first_time(samples: list[dict], predicate) -> float | None:
    for item in samples:
        if predicate(item):
            return _time(item)
    return None


def find_event_markers(
    samples: list[dict],
    *,
    wheel_threshold: float = 0.02,
    body_speed_threshold: float = 0.01,
    wheel_target_fraction: float = 0.90,
    body_settle_window_s: float = 0.25,
) -> dict[str, float | None]:
    """Find T0-T5 from an already annotated trace.

    T5 is the final sample in the trace, deliberately not described as an
    asymptotic settle unless the caller collected a sustained final window.
    """
    if not samples:
        return {key: None for key in ("T0", "T1", "T2", "T3", "T4", "T5")}
    body_speed_from_samples(samples)
    t0 = _first_time(
        samples,
        lambda s: abs(float((s.get("command") or {}).get("linear_x", 0.0))) > 1e-9
        or abs(float((s.get("command") or {}).get("angular_z", 0.0))) > 1e-9,
    )
    if t0 is None:
        return {key: None for key in ("T0", "T1", "T2", "T3", "T4", "T5")}
    active = [s for s in samples if _time(s) >= t0 and (
        abs(float((s.get("command") or {}).get("linear_x", 0.0))) > 1e-9
        or abs(float((s.get("command") or {}).get("angular_z", 0.0))) > 1e-9
    )]
    target = max(
        max(abs(float(_joint(s, "wheel_left_joint").get("velocity", 0.0))) for s in active),
        max(abs(float(_joint(s, "wheel_right_joint").get("velocity", 0.0))) for s in active),
    )
    t1 = _first_time(
        active,
        lambda s: target > 0.0
        and abs(float(_joint(s, "wheel_left_joint").get("velocity", 0.0))) >= target * wheel_target_fraction
        and abs(float(_joint(s, "wheel_right_joint").get("velocity", 0.0))) >= target * wheel_target_fraction,
    )
    active_last_time = max((_time(s) for s in active), default=t0)
    t2 = _first_time(
        [s for s in samples if _time(s) > active_last_time],
        lambda s: abs(float((s.get("command") or {}).get("linear_x", 0.0))) <= 1e-9
        and abs(float((s.get("command") or {}).get("angular_z", 0.0))) <= 1e-9,
    )
    t3 = None
    if t2 is not None:
        t3 = _first_time(
            [s for s in samples if _time(s) >= t2],
            lambda s: abs(float(_joint(s, "wheel_left_joint").get("velocity", 0.0))) < wheel_threshold
            and abs(float(_joint(s, "wheel_right_joint").get("velocity", 0.0))) < wheel_threshold,
        )
    t4 = None
    if t2 is not None:
        post_zero = [s for s in samples if _time(s) >= t2]
        for candidate in post_zero:
            end = _time(candidate) + body_settle_window_s
            window = [s for s in post_zero if _time(candidate) <= _time(s) <= end]
            if len(window) < 2:
                continue
            if all(
                float((s.get("derived") or {}).get("ground_linear_speed_mps", math.inf)) < body_speed_threshold
                and float((s.get("derived") or {}).get("ground_angular_speed_rps", math.inf)) < body_speed_threshold
                for s in window
            ):
                t4 = _time(candidate)
                break
    return {"T0": t0, "T1": t1, "T2": t2, "T3": t3, "T4": t4, "T5": _time(samples[-1])}


def _sample_at_or_after(samples: list[dict], timestamp: float) -> dict:
    return min(samples, key=lambda item: abs(_time(item) - timestamp))


def _distance(a: dict, b: dict) -> float:
    pa = _ground(a)
    pb = _ground(b)
    return math.hypot(float(pb.get("x", 0.0)) - float(pa.get("x", 0.0)), float(pb.get("y", 0.0)) - float(pa.get("y", 0.0)))


def segment_stop_distances(samples: list[dict], markers: dict[str, float | None]) -> dict[str, float | None]:
    """Partition ground-truth XY displacement into D1, D2, and D3."""
    values = {key: markers.get(key) for key in ("T2", "T3", "T4", "T5")}
    if any(value is None for value in values.values()):
        return {"D1_m": None, "D2_m": None, "D3_m": None, "D_total_m": None}
    points = {key: _sample_at_or_after(samples, float(value)) for key, value in values.items()}
    d1 = _distance(points["T2"], points["T3"])
    d2 = _distance(points["T3"], points["T4"])
    d3 = _distance(points["T4"], points["T5"])
    return {"D1_m": d1, "D2_m": d2, "D3_m": d3, "D_total_m": d1 + d2 + d3}


def _relative_yaw(samples: list[dict]) -> list[float]:
    initial = float(_ground(samples[0]).get("yaw", 0.0))
    return [wrap_angle(float(_ground(item).get("yaw", 0.0)) - initial) for item in samples]


def mirror_symmetry_metrics(ccw: list[dict], cw: list[dict]) -> dict[str, float]:
    """Compare same-time-index mirrored traces; inputs are sampled at one rate."""
    count = min(len(ccw), len(cw))
    if count == 0:
        raise ValueError("cannot compare empty traces")
    ccw_yaw = _relative_yaw(ccw[:count])
    cw_yaw = _relative_yaw(cw[:count])
    left_mismatch = []
    right_mismatch = []
    yaw_mismatch = []
    translation_mismatch = []
    ccw0 = _ground(ccw[0])
    cw0 = _ground(cw[0])
    for index in range(count):
        left_mismatch.append(abs(float(_joint(ccw[index], "wheel_left_joint").get("velocity", 0.0)) + float(_joint(cw[index], "wheel_left_joint").get("velocity", 0.0))))
        right_mismatch.append(abs(float(_joint(ccw[index], "wheel_right_joint").get("velocity", 0.0)) + float(_joint(cw[index], "wheel_right_joint").get("velocity", 0.0))))
        yaw_mismatch.append(abs(math.degrees(wrap_angle(ccw_yaw[index] + cw_yaw[index]))))
        ccw_dx = float(_ground(ccw[index]).get("x", 0.0)) - float(ccw0.get("x", 0.0))
        ccw_dy = float(_ground(ccw[index]).get("y", 0.0)) - float(ccw0.get("y", 0.0))
        cw_dx = float(_ground(cw[index]).get("x", 0.0)) - float(cw0.get("x", 0.0))
        cw_dy = float(_ground(cw[index]).get("y", 0.0)) - float(cw0.get("y", 0.0))
        translation_mismatch.append(math.hypot(ccw_dx + cw_dx, ccw_dy + cw_dy))
    return {
        "max_left_velocity_mismatch_rad_s": max(left_mismatch),
        "max_right_velocity_mismatch_rad_s": max(right_mismatch),
        "max_yaw_symmetry_error_deg": max(yaw_mismatch),
        "max_translation_symmetry_error_m": max(translation_mismatch),
    }
