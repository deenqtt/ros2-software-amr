"""goal_guard: the keep-out test the relay applies to a goal."""

from __future__ import annotations

from app.goal_guard import keepout_at

SQUARE = "[[0, 0], [2, 0], [2, 2], [0, 2]]"


def row(kind: str = "keepout", enabled: int = 1, name: str = "Panel", polygon=SQUARE) -> dict:
    return {"kind": kind, "enabled": enabled, "name": name, "polygon": polygon}


def test_names_the_enabled_keepout_a_point_is_in() -> None:
    assert keepout_at([row()], 1.0, 1.0) == "Panel"
    assert keepout_at([row()], 3.0, 1.0) is None


def test_ignores_switched_off_keepouts_and_other_kinds() -> None:
    assert keepout_at([row(enabled=0)], 1.0, 1.0) is None
    assert keepout_at([row(kind="avoid"), row(kind="speed")], 1.0, 1.0) is None


def test_survives_polygons_it_cannot_read() -> None:
    assert keepout_at([row(polygon="not json"), row(polygon="[[0, 0], [1, 1]]")], 0.5, 0.5) is None
