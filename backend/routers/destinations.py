"""
CRUD endpoints for destination points.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from database import get_db
from models import DestinationIn, DestinationOut

router = APIRouter(prefix="/api/destinations", tags=["destinations"])


@router.get("", response_model=List[DestinationOut])
def list_destinations(map_id: Optional[int] = None):
    with get_db() as con:
        if map_id is not None:
            rows = con.execute(
                "SELECT * FROM destinations WHERE map_id = ? OR map_id IS NULL ORDER BY id", (map_id,)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM destinations ORDER BY id"
            ).fetchall()
    return [dict(r) for r in rows]


@router.post("", response_model=DestinationOut, status_code=201)
def create_destination(body: DestinationIn):
    with get_db() as con:
        cur = con.execute(
            "INSERT INTO destinations (map_id, name, x, y, yaw, station_type) VALUES (?, ?, ?, ?, ?, ?)",
            (body.map_id, body.name, body.x, body.y, body.yaw, body.station_type),
        )
        row = con.execute(
            "SELECT * FROM destinations WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


@router.put("/{dest_id}", response_model=DestinationOut)
def update_destination(dest_id: int, body: DestinationIn):
    with get_db() as con:
        con.execute(
            "UPDATE destinations SET name = ?, x = ?, y = ?, yaw = ?, station_type = ? WHERE id = ?",
            (body.name, body.x, body.y, body.yaw, body.station_type, dest_id),
        )
        row = con.execute(
            "SELECT * FROM destinations WHERE id = ?", (dest_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Destination not found")
    return dict(row)


@router.delete("/{dest_id}", status_code=204)
def delete_destination(dest_id: int):
    with get_db() as con:
        con.execute("DELETE FROM destinations WHERE id = ?", (dest_id,))
