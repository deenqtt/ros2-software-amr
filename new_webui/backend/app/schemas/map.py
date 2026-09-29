"""Request and response models for the map registry."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    version: int
    content_hash: str
    # The filenames inside this map's directory. A client caching the pair
    # locally has to store the image under exactly the name the stored yaml
    # refers to, or map_server cannot resolve it.
    yaml_file: str
    image_file: str
    image_bytes: int
    resolution: float | None
    width: int | None
    height: int | None
    origin_x: float | None
    origin_y: float | None
    origin_yaw: float | None
    negate: int | None
    occupied_thresh: float | None
    free_thresh: float | None
    created_by_robot_id: str | None
    note: str | None
    created_at: str


class MapRenameIn(BaseModel):
    """
    Rename a map lineage.

    The name is shared by every version, so this renames all of them. Renaming
    one version alone would leave the rest behind under the old name and start
    the new name at whatever version number that row happened to hold.
    """

    model_config = ConfigDict(extra="forbid")

    name: str


class AssignMapIn(BaseModel):
    """
    Point a robot at a map.

    `null` clears the assignment, which is how a robot is taken off a map
    without being deleted.
    """

    model_config = ConfigDict(extra="forbid")

    map_id: str | None
