"""
Zone polygons to costmap filter mask values. Pure Python, no ROS imports.

zone_mask_server owns the topics; this owns the arithmetic, so the part that
decides what the robot may drive through is unit-tested without a robot.

Four masks, one per filter Nav2 reads:

  keepout  100 inside every keepout polygon, plus a *halo* around it.
  avoid    avoid polygons only, the UI's 1..99 mapped onto 8..80.
  speed    a maximum speed, encoded as round(m/s * 100).
  binary   100 inside every binary polygon.

Why the keepout halo
--------------------
Costmap filters are written into the costmap *after* inflation, and are never
inflated themselves. A keepout therefore marks exactly the cells the operator
drew and nothing around them. The planners and MPPI check the full robot
footprint only once the cost at the robot's centre reaches the circumscribed
cost (about 136 on the costmap scale for this robot, i.e. a mask value of about
54); below that they check the centre point alone. So without a halo the centre
stops at the polygon edge while the body — 0.78 m long — is already half way
in, and the next step finds the footprint in lethal cost with no way out: MPPI
reports "Optimizer fail to compute path" and the robot sits there.

The halo is a band of falling, never lethal, cost round each keepout: high
enough (from 95 at the edge down to 60 at the outer rim) that the footprint is
checked all through it, low enough that the robot may still pass through the
band when that is the only way. 60 rather than the bare minimum of 54 leaves a
margin: the threshold follows the inflation layer (radius 0.51, cost scaling 3.1
today), so recheck it if those change. Its default width, 0.6 m, is more than the
circumscribed radius (0.49 m) with a couple of cells to spare, so the whole body
is being checked before any part of it can reach the keepout.

Why the halo stops at walls
---------------------------
The halo is only there to stop the robot's body reaching the keepout, and a body
cannot reach it through a wall. Measured in a straight line it went straight
through them: a keepout drawn in a room behind a corridor wall filled half of a
1 m corridor with halo, squeezed the planned path against the opposite wall
until a footprint corner touched a wall pixel, and the planner then refused
every start ("Start occupied") with the robot standing in an empty corridor.

So when the map is known, a cell only gets a halo if it can be *reached* from
the part of the keepout that is not itself wall, within the halo's width,
going round walls rather than through them. A cell that can still has the value
its straight-line distance gives it, so in open space the halo is exactly what
it always was. Walls are grown by one cell first: SLAM walls have pinholes, and
a halo must not leak through a one-pixel gap the robot could never use.

Why the avoid mask is separate and stops at 80
----------------------------------------------
Avoid zones used to share the keepout mask. Now the keepout mask carries the
halo, and an avoid value above the halo's would make a "prefer not" area harder
to cross than the band round a "never". Values stop at 80 so an avoid zone is
always cheaper than lethal and than the inner halo, and start at 8 so the
slightest preference still registers against ordinary free space.

Why speed is round(m/s * 100)
-----------------------------
SpeedFilter with type 2 (absolute) reads limit = base + multiplier * value.
With base 0 and multiplier 0.01 a mask value is centimetres per second, which
gives 0.01 m/s steps across the robot's real range; 0.1 steps (the previous
multiplier) could not say 0.25 m/s. 0 in a speed mask means *no limit*, so a
limit is never allowed to round down to it.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

KEEPOUT_VALUE = 100
BINARY_VALUE = 100

# Halo defaults. See the module docstring for where the numbers come from.
HALO_WIDTH_M = 0.6
HALO_INNER = 95
HALO_OUTER = 60

# UI avoid_cost 1..99 onto these mask values.
AVOID_COST_MIN, AVOID_COST_MAX = 1, 99
AVOID_MASK_MIN, AVOID_MASK_MAX = 8, 80
AVOID_COST_DEFAULT = 50

# speed_limit = SPEED_BASE + SPEED_MULTIPLIER * mask value (SpeedFilter type 2).
SPEED_BASE = 0.0
SPEED_MULTIPLIER = 0.01
SPEED_MASK_MIN, SPEED_MASK_MAX = 1, 100
# What a speed zone with no usable limit gets. Slow rather than unrestricted:
# the previous server's fallback, kept so a malformed row errs on the safe side.
SPEED_FALLBACK_M_S = 0.1

MASKS = ("keepout", "avoid", "speed", "binary")

# OccupancyGrid values from this up are walls (map_server's occupied_thresh 0.65).
WALL_THRESHOLD = 65
# Cells walls are grown by before they stop a halo; see the module docstring.
WALL_GROW_CELLS = 1
# An 8-connected path is up to 8.24 % longer than the straight line it stands in
# for, so reachability allows that much, plus a cell for where the path starts.
OCTILE_SLACK = 1.0824


@dataclass(frozen=True)
class Grid:
    """The map's geometry: cells, metres per cell, and the cell (0, 0) corner."""

    width: int
    height: int
    resolution: float
    origin_x: float
    origin_y: float


@dataclass(frozen=True)
class Halo:
    width: float = HALO_WIDTH_M
    inner: int = HALO_INNER
    outer: int = HALO_OUTER


@dataclass
class Rasterised:
    masks: dict = field(default_factory=dict)  # name -> bytearray, row-major
    counts: dict = field(default_factory=dict)  # name -> zones drawn into it
    skipped: list = field(default_factory=list)  # human-readable reasons


def validate_halo(width: float, inner: int, outer: int) -> Halo:
    """
    The halo's parameters, or ValueError.

    Width 0 turns the halo off. Values must stay below 100: a lethal halo would
    be a bigger keepout than the one drawn, and the robot could no longer pass
    a keepout through a doorway it fits through.
    """
    width = float(width)
    inner = int(inner)
    outer = int(outer)
    if not math.isfinite(width) or width < 0.0:
        raise ValueError(f"keepout_halo_width must be >= 0 m, got {width!r}")
    if not 1 <= outer <= inner <= 99:
        raise ValueError(
            "keepout halo values must satisfy 1 <= outer <= inner <= 99, "
            f"got inner {inner}, outer {outer}"
        )
    return Halo(width, inner, outer)


def avoid_value(cost) -> int:
    """The UI's avoid_cost (1..99) as an avoid mask value (8..80)."""
    try:
        cost = float(cost)
    except (TypeError, ValueError):
        cost = AVOID_COST_DEFAULT
    if not math.isfinite(cost):
        cost = AVOID_COST_DEFAULT
    cost = max(AVOID_COST_MIN, min(AVOID_COST_MAX, cost))
    span = (AVOID_MASK_MAX - AVOID_MASK_MIN) / (AVOID_COST_MAX - AVOID_COST_MIN)
    return int(round(AVOID_MASK_MIN + (cost - AVOID_COST_MIN) * span))


def speed_value(limit) -> int:
    """
    A speed limit in m/s as a speed mask value, 1..100.

    Clamped to 1 at the bottom: 0 means *no restriction*, so rounding a very
    low limit down to zero would turn the slowest zone on the map into the
    fastest. A missing, zero or non-numeric limit gets SPEED_FALLBACK_M_S.
    """
    try:
        limit = float(limit)
    except (TypeError, ValueError):
        limit = SPEED_FALLBACK_M_S
    if not math.isfinite(limit) or limit <= 0.0:
        limit = SPEED_FALLBACK_M_S
    value = int(round((limit - SPEED_BASE) / SPEED_MULTIPLIER))
    return max(SPEED_MASK_MIN, min(SPEED_MASK_MAX, value))


def halo_value(distance: float, halo: Halo) -> int:
    """
    The halo's mask value at `distance` metres outside a keepout, or 0 beyond it.

    Linear from `inner` at the edge to `outer` at the rim. Never 100.
    """
    if halo.width <= 0.0 or distance < 0.0 or distance > halo.width:
        return 0
    value = halo.inner - (halo.inner - halo.outer) * (distance / halo.width)
    return max(halo.outer, min(halo.inner, int(round(value))))


def to_cells(polygon, grid: Grid) -> list[tuple[int, int]]:
    """Map-frame metres to cell indices. floor, so negatives land on the right cell."""
    return [
        (
            int(math.floor((float(point[0]) - grid.origin_x) / grid.resolution)),
            int(math.floor((float(point[1]) - grid.origin_y) / grid.resolution)),
        )
        for point in polygon
    ]


def fill_polygon(data: bytearray, vertices: list, width: int, height: int, value: int) -> None:
    """
    Scanline fill of a polygon given in cell indices.

    Writes the larger value when zones overlap, so a keepout drawn across a
    halo stays a keepout — the stricter rule wins rather than whichever polygon
    happened to be drawn last.
    """
    if len(vertices) < 3:
        return

    ys = [y for _, y in vertices]
    y_start = max(0, min(ys))
    y_end = min(height - 1, max(ys))

    count = len(vertices)
    for y in range(y_start, y_end + 1):
        crossings = []
        for i in range(count):
            x1, y1 = vertices[i]
            x2, y2 = vertices[(i + 1) % count]
            if y1 == y2:
                continue
            # Half-open test, so a vertex lying exactly on the scanline is
            # counted once rather than twice — otherwise the fill leaks.
            if (y1 <= y < y2) or (y2 <= y < y1):
                crossings.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))

        crossings.sort()
        for i in range(0, len(crossings) - 1, 2):
            x_start = max(0, int(round(crossings[i])))
            x_end = min(width - 1, int(round(crossings[i + 1])))
            row = y * width
            for x in range(x_start, x_end + 1):
                if value > data[row + x]:
                    data[row + x] = value


def _segment_distance(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _inside(px, py, polygon) -> bool:
    """Even-odd point in polygon, in metres."""
    inside = False
    count = len(polygon)
    for i in range(count):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % count]
        if (ay > py) != (by > py):
            if px < ax + (py - ay) * (bx - ax) / (by - ay):
                inside = not inside
    return inside


def walls_from_occupancy(
    data, width: int, height: int,
    threshold: int = WALL_THRESHOLD, grow: int = WALL_GROW_CELLS,
) -> bytearray:
    """
    The map's walls as a row-major bytearray (1 = wall), grown by `grow` cells.

    `data` is OccupancyGrid data: 0..100, -1 unknown. Unknown is not a wall: the
    halo is about what the robot can reach, and it is not driving into unknown.
    """
    walls = bytearray(width * height)
    for index, value in enumerate(data):
        if value >= threshold:
            walls[index] = 1
    for _ in range(max(0, int(grow))):
        grown = bytearray(walls)
        for j in range(height):
            row = j * width
            for i in range(width):
                if not walls[row + i]:
                    continue
                for dj in (-1, 0, 1):
                    jj = j + dj
                    if not 0 <= jj < height:
                        continue
                    for di in (-1, 0, 1):
                        ii = i + di
                        if 0 <= ii < width:
                            grown[jj * width + ii] = 1
        walls = grown
    return walls


def _reach(walls, inside, box, grid: Grid, limit: float) -> dict:
    """
    Path length (m) from the open part of a keepout to each cell within `limit`.

    Dijkstra over the cells of `box` (i_start, i_end, j_start, j_end) that are
    not walls, 8-connected, never cutting a wall's corner. Starts from every
    keepout cell that is not wall itself: a keepout whose edge runs along a wall
    is not reachable from the far side of that wall.
    """
    i_start, i_end, j_start, j_end = box
    width = grid.width
    res = grid.resolution
    diagonal = res * math.sqrt(2.0)
    best = {}
    queue = []
    for index in inside:
        if not walls[index]:
            best[index] = 0.0
            queue.append((0.0, index))
    heapq.heapify(queue)

    def free(i, j):
        return i_start <= i <= i_end and j_start <= j <= j_end and not walls[j * width + i]

    while queue:
        distance, index = heapq.heappop(queue)
        if distance > best.get(index, math.inf):
            continue
        j, i = divmod(index, width)
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            ni, nj = i + di, j + dj
            if not free(ni, nj):
                continue
            if di and dj and not (free(i + di, j) and free(i, j + dj)):
                continue
            step = diagonal if di and dj else res
            candidate = distance + step
            neighbour = nj * width + ni
            if candidate <= limit and candidate < best.get(neighbour, math.inf):
                best[neighbour] = candidate
                heapq.heappush(queue, (candidate, neighbour))
    return best


def draw_halo(
    data: bytearray, polygon, grid: Grid, halo: Halo, walls: bytearray | None = None,
) -> None:
    """
    Write the halo round one keepout polygon (metres), keeping the larger value.

    Measured from each cell's centre to the nearest polygon edge. Cells already
    at 100 are the keepout itself and are skipped, and so are cells whose centre
    lies inside the polygon — those belong to the fill, not to the halo.

    With `walls` (see walls_from_occupancy), a cell also has to be reachable
    from the keepout within the halo's width without crossing a wall; walls get
    no halo themselves. Without it, the halo is drawn through everything.
    """
    if halo.width <= 0.0 or len(polygon) < 3:
        return
    points = [(float(x), float(y)) for x, y in polygon]
    res = grid.resolution
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    i_start = max(0, int(math.floor((min(xs) - halo.width - grid.origin_x) / res)))
    i_end = min(grid.width - 1, int(math.floor((max(xs) + halo.width - grid.origin_x) / res)))
    j_start = max(0, int(math.floor((min(ys) - halo.width - grid.origin_y) / res)))
    j_end = min(grid.height - 1, int(math.floor((max(ys) + halo.width - grid.origin_y) / res)))
    edges = [
        (points[i][0], points[i][1], points[(i + 1) % len(points)][0],
         points[(i + 1) % len(points)][1])
        for i in range(len(points))
    ]

    reach = None
    if walls is not None:
        inside = [
            j * grid.width + i
            for j in range(j_start, j_end + 1)
            for i in range(i_start, i_end + 1)
            if _inside(grid.origin_x + (i + 0.5) * res, grid.origin_y + (j + 0.5) * res, points)
        ]
        reach = _reach(
            walls, inside, (i_start, i_end, j_start, j_end), grid,
            halo.width * OCTILE_SLACK + res,
        )

    for j in range(j_start, j_end + 1):
        cy = grid.origin_y + (j + 0.5) * res
        row = j * grid.width
        for i in range(i_start, i_end + 1):
            index = row + i
            if data[index] >= KEEPOUT_VALUE:
                continue
            if reach is not None and index not in reach:
                continue
            cx = grid.origin_x + (i + 0.5) * res
            distance = min(_segment_distance(cx, cy, *edge) for edge in edges)
            value = halo_value(distance, halo)
            if value <= data[index]:
                continue
            if _inside(cx, cy, points):
                continue
            data[index] = value


def rasterise(
    zones: list, grid: Grid, halo: Halo = Halo(), walls: bytearray | None = None,
) -> Rasterised:
    """
    Every enabled zone into its mask. Masks are row-major bytearrays.

    All keepout polygons are filled before any halo is drawn, so a halo never
    lowers — or even looks at — a cell another keepout already owns. `walls`,
    when given, stops the halo at walls (see draw_halo).
    """
    out = Rasterised(
        masks={name: bytearray(grid.width * grid.height) for name in MASKS},
        counts={name: 0 for name in MASKS},
    )
    keepouts = []

    for zone in zones:
        if not isinstance(zone, dict) or not zone.get("enabled", True):
            continue
        polygon = zone.get("polygon") or []
        if len(polygon) < 3:
            continue

        kind = str(zone.get("kind", "keepout"))
        if kind == "keepout":
            target, value = "keepout", KEEPOUT_VALUE
            keepouts.append(polygon)
        elif kind == "avoid":
            target, value = "avoid", avoid_value(zone.get("avoid_cost"))
        elif kind == "speed":
            target, value = "speed", speed_value(zone.get("speed_limit"))
        elif kind == "binary":
            target, value = "binary", BINARY_VALUE
        else:
            out.skipped.append(f'unknown zone kind "{kind}"')
            continue

        fill_polygon(out.masks[target], to_cells(polygon, grid), grid.width, grid.height, value)
        out.counts[target] += 1

    for polygon in keepouts:
        draw_halo(out.masks["keepout"], polygon, grid, halo, walls)
    return out


def keepout_at(zones: list, x: float, y: float) -> str | None:
    """
    The name of the enabled keep-out zone that (x, y), in metres, lies in.

    None when there is none. A goal there can never be reached — the planner
    treats a keep-out as lethal — and Nav2 would otherwise spend minutes on
    recoveries against an area that will not move. Same polygon rule as the
    fill, so a point refused here is a point the mask covers.
    """
    for zone in zones or []:
        if not isinstance(zone, dict) or not zone.get("enabled", True):
            continue
        if str(zone.get("kind", "keepout")) != "keepout":
            continue
        polygon = zone.get("polygon") or []
        if len(polygon) < 3:
            continue
        try:
            points = [(float(px), float(py)) for px, py in polygon]
        except (TypeError, ValueError):
            continue
        if _inside(float(x), float(y), points):
            return str(zone.get("name") or zone.get("id") or "keep-out")
    return None
