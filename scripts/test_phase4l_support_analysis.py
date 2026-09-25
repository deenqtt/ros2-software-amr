#!/usr/bin/env python3
"""Tests for Phase 4L support-polygon calculations."""

import math

from phase4l_support_analysis import (
    CANDIDATE_POINTS,
    classify_support,
    convex_hull,
    polygon_area,
)


COM = (0.002581, 0.0)


def test_four_point_polygon_is_diamond_and_contains_com():
    hull = convex_hull(CANDIDATE_POINTS["A_four_point"])
    assert math.isclose(polygon_area(hull), 0.1008, rel_tol=1e-9)
    result = classify_support(hull, COM)
    assert result.inside is True
    assert math.isclose(result.min_boundary_distance, 0.1563415242, abs_tol=1e-6)


def test_rear_three_point_polygon_contains_com():
    hull = convex_hull(CANDIDATE_POINTS["B_rear_three_point"])
    assert math.isclose(polygon_area(hull), 0.0504, rel_tol=1e-9)
    result = classify_support(hull, COM)
    assert result.inside is False
    assert math.isclose(result.min_boundary_distance, -0.0025809717, abs_tol=1e-6)


def test_front_three_point_polygon_contains_com():
    hull = convex_hull(CANDIDATE_POINTS["C_front_three_point"])
    assert math.isclose(polygon_area(hull), 0.0504, rel_tol=1e-9)
    result = classify_support(hull, COM)
    assert result.inside is True
    assert math.isclose(result.rear_margin_m, 0.0025809717, abs_tol=1e-6)


if __name__ == "__main__":
    test_four_point_polygon_is_diamond_and_contains_com()
    test_rear_three_point_polygon_contains_com()
    test_front_three_point_polygon_contains_com()
    print("phase4l support-analysis tests passed")
