#!/usr/bin/env python3
"""Support-polygon calculations for the Phase 4L disposable candidates."""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

Point = tuple[float, float]

DRIVE_LEFT = (0.0, 0.21)
DRIVE_RIGHT = (0.0, -0.21)
FRONT_CASTER = (0.24, 0.0)
REAR_CASTER = (-0.24, 0.0)

CANDIDATE_POINTS: dict[str, tuple[Point, ...]] = {
    "A_four_point": (DRIVE_LEFT, DRIVE_RIGHT, FRONT_CASTER, REAR_CASTER),
    "B_rear_three_point": (DRIVE_LEFT, DRIVE_RIGHT, REAR_CASTER),
    "C_front_three_point": (DRIVE_LEFT, DRIVE_RIGHT, FRONT_CASTER),
}


@dataclasses.dataclass(frozen=True)
class SupportResult:
    polygon: tuple[Point, ...]
    area_m2: float
    inside: bool
    boundary_distances_m: tuple[float, ...]
    min_boundary_distance: float
    front_margin_m: float
    rear_margin_m: float


def cross(origin: Point, a: Point, b: Point) -> float:
    return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])


def convex_hull(points: tuple[Point, ...] | list[Point]) -> tuple[Point, ...]:
    """Return a counter-clockwise monotonic-chain hull without duplicates."""
    unique = sorted(set(points))
    if len(unique) <= 1:
        return tuple(unique)

    lower: list[Point] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[Point] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return tuple(lower[:-1] + upper[:-1])


def polygon_area(polygon: tuple[Point, ...]) -> float:
    return abs(sum(
        polygon[index][0] * polygon[(index + 1) % len(polygon)][1]
        - polygon[(index + 1) % len(polygon)][0] * polygon[index][1]
        for index in range(len(polygon))
    )) / 2.0


def classify_support(polygon: tuple[Point, ...], com: Point) -> SupportResult:
    if len(polygon) < 3:
        raise ValueError("support polygon needs at least three vertices")
    distances: list[float] = []
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        edge_x = end[0] - start[0]
        edge_y = end[1] - start[1]
        signed_cross = edge_x * (com[1] - start[1]) - edge_y * (com[0] - start[0])
        distances.append(signed_cross / math.hypot(edge_x, edge_y))
    return SupportResult(
        polygon=polygon,
        area_m2=polygon_area(polygon),
        inside=all(distance >= -1e-12 for distance in distances),
        boundary_distances_m=tuple(distances),
        min_boundary_distance=min(distances),
        front_margin_m=max(point[0] for point in polygon) - com[0],
        rear_margin_m=com[0] - min(point[0] for point in polygon),
    )


def parse_mass_and_com(sdf: Path) -> tuple[float, Point, float]:
    root = ET.parse(sdf).getroot()
    model = root.find("model")
    if model is None:
        raise ValueError("SDF has no model")
    total_mass = 0.0
    weighted_x = weighted_y = weighted_z = 0.0
    for link in model.findall("link"):
        inertial = link.find("inertial")
        if inertial is None or inertial.findtext("mass") is None:
            continue
        mass = float(inertial.findtext("mass"))
        link_pose = [float(value) for value in (link.findtext("pose") or "0 0 0 0 0 0").split()]
        inertial_pose = [float(value) for value in (inertial.findtext("pose") or "0 0 0 0 0 0").split()]
        x = link_pose[0] + inertial_pose[0]
        y = link_pose[1] + inertial_pose[1]
        z = link_pose[2] + inertial_pose[2]
        total_mass += mass
        weighted_x += mass * x
        weighted_y += mass * y
        weighted_z += mass * z
    return total_mass, (weighted_x / total_mass, weighted_y / total_mass), weighted_z / total_mass


def analyse(sdf: Path) -> dict:
    total_mass, com_xyz, com_z = parse_mass_and_com(sdf)
    com = (com_xyz[0], com_xyz[1])
    result = {
        "sdf": str(sdf),
        "mass_kg": total_mass,
        "com_m": {"x": com[0], "y": com[1], "z": com_z},
        "candidates": {},
    }
    for name, points in CANDIDATE_POINTS.items():
        summary = classify_support(convex_hull(points), com)
        result["candidates"][name] = dataclasses.asdict(summary)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdf", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyse(args.sdf)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
