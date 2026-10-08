"""zone_raster: zone polygons to costmap filter mask values."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zone_raster import (  # noqa: E402
    Grid,
    Halo,
    avoid_value,
    draw_halo,
    fill_polygon,
    halo_value,
    rasterise,
    speed_value,
    to_cells,
    validate_halo,
)

# 10 m x 10 m at 0.05 m/cell, origin at (-5, -5): the map centre is (0, 0).
GRID = Grid(width=200, height=200, resolution=0.05, origin_x=-5.0, origin_y=-5.0)
SQUARE = [[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]]


def cell_at(mask, x, y, grid=GRID):
    i = int((x - grid.origin_x) // grid.resolution)
    j = int((y - grid.origin_y) // grid.resolution)
    return mask[j * grid.width + i]


def zone(kind, polygon=SQUARE, **extra):
    return {"kind": kind, "polygon": polygon, "enabled": True, **extra}


# ── Polygon fill ────────────────────────────────────────────────────────────


def test_fill_covers_the_inside_and_nothing_far_outside():
    data = bytearray(GRID.width * GRID.height)
    fill_polygon(data, to_cells(SQUARE, GRID), GRID.width, GRID.height, 100)
    assert cell_at(data, 0.0, 0.0) == 100
    assert cell_at(data, 0.9, 0.9) == 100
    assert cell_at(data, -0.9, -0.9) == 100
    assert cell_at(data, 1.2, 0.0) == 0
    assert cell_at(data, 0.0, -1.2) == 0


def test_fill_keeps_the_larger_value():
    data = bytearray(GRID.width * GRID.height)
    cells = to_cells(SQUARE, GRID)
    fill_polygon(data, cells, GRID.width, GRID.height, 100)
    fill_polygon(data, cells, GRID.width, GRID.height, 40)
    assert cell_at(data, 0.0, 0.0) == 100


def test_fill_clips_a_polygon_that_leaves_the_map():
    data = bytearray(GRID.width * GRID.height)
    off_edge = [[-7.0, -7.0], [-4.0, -7.0], [-4.0, -4.0], [-7.0, -4.0]]
    fill_polygon(data, to_cells(off_edge, GRID), GRID.width, GRID.height, 100)
    assert cell_at(data, -4.9, -4.9) == 100
    assert len(data) == GRID.width * GRID.height


def test_negative_coordinates_floor_to_the_right_cell():
    grid = Grid(width=10, height=10, resolution=1.0, origin_x=0.0, origin_y=0.0)
    # -0.5 is one cell left of the map, not cell 0.
    assert to_cells([[-0.5, 2.5]], grid) == [(-1, 2)]


# ── Halo ────────────────────────────────────────────────────────────────────


def test_halo_value_runs_from_inner_to_outer():
    halo = Halo(width=0.6, inner=95, outer=55)
    assert halo_value(0.0, halo) == 95
    assert halo_value(0.3, halo) == 75
    assert halo_value(0.6, halo) == 55
    assert halo_value(0.61, halo) == 0


def test_halo_value_is_never_lethal_and_off_at_width_zero():
    halo = Halo(width=0.6, inner=95, outer=55)
    assert all(halo_value(d / 100, halo) < 100 for d in range(0, 70))
    assert halo_value(0.0, Halo(width=0.0)) == 0


def test_halo_around_a_keepout_falls_with_distance():
    masks = rasterise([zone("keepout")], GRID).masks["keepout"]
    assert cell_at(masks, 0.0, 0.0) == 100
    # Cell centres just outside the right edge (x = 1.0), on the y = 0.025 row.
    near = cell_at(masks, 1.06, 0.01)   # centre 1.075 m: 0.075 m out
    mid = cell_at(masks, 1.31, 0.01)    # centre 1.325 m: 0.325 m out
    far = cell_at(masks, 1.56, 0.01)    # centre 1.575 m: 0.575 m out
    assert near == halo_value(0.075, Halo())
    assert mid == halo_value(0.325, Halo())
    assert far == halo_value(0.575, Halo())
    assert 95 >= near > mid > far >= 55
    assert cell_at(masks, 1.7, 0.0) == 0


def test_halo_reaches_round_a_corner_by_distance_not_by_box():
    masks = rasterise([zone("keepout")], GRID).masks["keepout"]
    # 0.5 m diagonally off the (1, 1) corner is 0.707 m away: outside the halo.
    assert cell_at(masks, 1.5, 1.5) == 0
    # 0.3 m diagonally is 0.42 m away: inside it.
    assert 55 <= cell_at(masks, 1.3, 1.3) < 100


def test_no_halo_cell_is_ever_100():
    keepout = rasterise([zone("keepout")], GRID).masks["keepout"]
    inside = bytearray(GRID.width * GRID.height)
    fill_polygon(inside, to_cells(SQUARE, GRID), GRID.width, GRID.height, 100)
    for index, value in enumerate(keepout):
        if inside[index] == 0:
            assert value < 100


def test_halos_of_two_keepouts_combine_by_max():
    left = [[-2.0, -1.0], [-1.0, -1.0], [-1.0, 1.0], [-2.0, 1.0]]
    right = [[-0.2, -1.0], [0.8, -1.0], [0.8, 1.0], [-0.2, 1.0]]
    masks = rasterise([zone("keepout", left), zone("keepout", right)], GRID).masks["keepout"]
    # Between the two, 0.8 m wide: each cell gets the value of its nearer edge.
    # Cell centres, so the lookup does not fall on a cell boundary.
    assert cell_at(masks, -0.925, 0.0) == halo_value(0.075, Halo())  # 0.075 m from left
    assert cell_at(masks, -0.275, 0.0) == halo_value(0.075, Halo())  # 0.075 m from right
    assert cell_at(masks, -0.625, 0.0) == halo_value(0.375, Halo())  # 0.375 / 0.425


def test_a_halo_never_lowers_another_keepout():
    a = [[-1.0, -1.0], [0.0, -1.0], [0.0, 1.0], [-1.0, 1.0]]
    b = [[0.2, -1.0], [1.0, -1.0], [1.0, 1.0], [0.2, 1.0]]
    masks = rasterise([zone("keepout", a), zone("keepout", b)], GRID).masks["keepout"]
    assert cell_at(masks, 0.5, 0.0) == 100
    assert cell_at(masks, -0.5, 0.0) == 100


def test_halo_width_zero_draws_only_the_polygon():
    masks = rasterise([zone("keepout")], GRID, Halo(width=0.0)).masks["keepout"]
    assert cell_at(masks, 1.2, 0.0) == 0
    assert cell_at(masks, 0.0, 0.0) == 100


def test_draw_halo_skips_cells_inside_the_polygon():
    data = bytearray(GRID.width * GRID.height)
    draw_halo(data, SQUARE, GRID, Halo())
    # Without a fill first, the inside stays empty rather than becoming halo.
    assert cell_at(data, 0.0, 0.0) == 0
    assert cell_at(data, 1.1, 0.0) > 0


@pytest.mark.parametrize(
    ("width", "inner", "outer"),
    [(-0.1, 95, 55), (0.6, 100, 55), (0.6, 50, 55), (0.6, 95, 0), (float("nan"), 95, 55)],
)
def test_validate_halo_refuses_bad_settings(width, inner, outer):
    with pytest.raises(ValueError):
        validate_halo(width, inner, outer)


def test_validate_halo_accepts_the_defaults():
    assert validate_halo(0.6, 95, 55) == Halo(0.6, 95, 55)


# ── Avoid ───────────────────────────────────────────────────────────────────


def test_avoid_maps_1_to_99_onto_8_to_80():
    assert avoid_value(1) == 8
    assert avoid_value(99) == 80
    assert avoid_value(50) == 44
    values = [avoid_value(cost) for cost in range(1, 100)]
    assert values == sorted(values)
    assert all(8 <= value <= 80 for value in values)


def test_avoid_clamps_and_defaults():
    assert avoid_value(0) == 8
    assert avoid_value(250) == 80
    assert avoid_value(None) == avoid_value(50)
    assert avoid_value("x") == avoid_value(50)


def test_avoid_goes_to_its_own_mask_and_not_the_keepout_one():
    out = rasterise([zone("avoid", avoid_cost=99)], GRID)
    assert cell_at(out.masks["avoid"], 0.0, 0.0) == 80
    assert not any(out.masks["keepout"])
    assert max(out.masks["avoid"]) <= 80
    assert out.counts["avoid"] == 1


# ── Speed ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("limit", "value"),
    [(0.3, 30), (0.25, 25), (0.6, 60), (1.0, 100), (5.0, 100), (0.001, 1), (0.004, 1)],
)
def test_speed_is_centimetres_per_second_clamped_1_to_100(limit, value):
    assert speed_value(limit) == value


@pytest.mark.parametrize("limit", [None, 0, -0.3, "fast", float("nan")])
def test_speed_without_a_usable_limit_falls_back_to_slow(limit):
    assert speed_value(limit) == 10


def test_speed_zone_is_written_to_the_speed_mask():
    out = rasterise([zone("speed", speed_limit=0.3)], GRID)
    assert cell_at(out.masks["speed"], 0.0, 0.0) == 30
    assert cell_at(out.masks["speed"], 2.0, 0.0) == 0
    assert not any(out.masks["keepout"])


# ── Everything together ─────────────────────────────────────────────────────


def test_binary_and_disabled_and_unknown_zones():
    out = rasterise(
        [
            zone("binary"),
            {**zone("keepout"), "enabled": False},
            zone("teleport"),
            zone("keepout", [[0.0, 0.0], [1.0, 1.0]]),
        ],
        GRID,
    )
    assert cell_at(out.masks["binary"], 0.0, 0.0) == 100
    assert not any(out.masks["keepout"])
    assert out.counts == {"keepout": 0, "avoid": 0, "speed": 0, "binary": 1}
    assert out.skipped == ['unknown zone kind "teleport"']


def test_avoid_and_halo_never_produce_100():
    out = rasterise(
        [zone("keepout"), zone("avoid", [[1.0, -1.0], [3.0, -1.0], [3.0, 1.0], [1.0, 1.0]],
                               avoid_cost=99)],
        GRID,
    )
    assert 100 not in out.masks["avoid"]
    # The avoid zone touching the keepout does not leak into the keepout mask.
    assert cell_at(out.masks["keepout"], 2.5, 0.0) == 0
