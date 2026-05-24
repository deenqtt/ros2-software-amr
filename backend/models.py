"""
Pydantic schemas for request/response validation.
"""
from typing import Optional, List
from pydantic import BaseModel


# ── Maps ─────────────────────────────────────────────────────────────────────

class MapOut(BaseModel):
    id: int
    name: str
    yaml_file: str
    resolution: Optional[float]
    width: Optional[int]
    height: Optional[int]
    origin_x: Optional[float]
    origin_y: Optional[float]
    created_at: str


class MapActivateOut(BaseModel):
    yaml_path: str


# ── Missions ──────────────────────────────────────────────────────────────────

class WaypointItem(BaseModel):
    name: str
    x: float
    y: float
    theta: float = 0.0
    task: str = 'Pick'          # Pick | Drop
    continue_mode: str = 'Auto' # Auto | Manual


class MissionIn(BaseModel):
    name: str
    map_id: Optional[int] = None
    waypoints: List[WaypointItem]
    loop: bool = False
    loop_count: int = 0


class MissionOut(BaseModel):
    id: int
    name: str
    map_id: Optional[int]
    waypoints: List[WaypointItem]
    loop: bool
    loop_count: int
    created_at: str


# ── Keepout Zones ─────────────────────────────────────────────────────────────

class PointXY(BaseModel):
    x: float
    y: float


class KeepoutIn(BaseModel):
    map_id: int
    name: str
    polygon: List[PointXY]


class KeepoutOut(BaseModel):
    id: int
    map_id: int
    name: str
    polygon: List[PointXY]


# ── Destination Points ────────────────────────────────────────────────────────
# station_type: 0=Pick, 1=Drop, 2=Pick & Drop

class DestinationIn(BaseModel):
    map_id: Optional[int] = None
    name: str
    x: float
    y: float
    yaw: float = 0.0
    station_type: int = 2  # default: Pick & Drop


class DestinationOut(BaseModel):
    id: int
    map_id: Optional[int]
    name: str
    x: float
    y: float
    yaw: float
    station_type: int
    created_at: str


# ── Dock Stations ─────────────────────────────────────────────────────────────

class DockPoint(BaseModel):
    x: float
    y: float
    yaw: float = 0.0


class DockIn(BaseModel):
    map_id: Optional[int] = None
    name: str
    target: DockPoint


class DockOut(BaseModel):
    id: int
    map_id: Optional[int]
    name: str
    target: DockPoint
