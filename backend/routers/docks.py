"""
Dock stations router.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from models import DockIn, DockOut, DockPoint

router = APIRouter(prefix="/api/docks", tags=["docks"])


def _row_to_dock(row) -> DockOut:
    return DockOut(
        id=row["id"],
        map_id=row["map_id"],
        name=row["name"],
        target=DockPoint(x=row["x"], y=row["y"], yaw=row["theta"] or 0.0),
    )


@router.get("", response_model=list[DockOut])
def list_docks(map_id: Optional[int] = Query(None)):
    with get_db() as db:
        if map_id is not None:
            rows = db.execute(
                "SELECT * FROM dock_stations WHERE map_id = ?", (map_id,)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM dock_stations").fetchall()
    return [_row_to_dock(r) for r in rows]


@router.post("", response_model=DockOut)
def create_dock(body: DockIn):
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO dock_stations
               (map_id, name, x, y, theta, approach_x, approach_y, approach_yaw)
               VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL)""",
            (body.map_id, body.name, body.target.x, body.target.y, body.target.yaw),
        )
        row = db.execute("SELECT * FROM dock_stations WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_dock(row)


@router.put("/{dock_id}", response_model=DockOut)
def update_dock(dock_id: int, body: DockIn):
    with get_db() as db:
        row = db.execute("SELECT id FROM dock_stations WHERE id = ?", (dock_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Dock station not found")
        db.execute(
            """UPDATE dock_stations
               SET map_id=?, name=?, x=?, y=?, theta=?, approach_x=NULL, approach_y=NULL, approach_yaw=NULL
               WHERE id=?""",
            (body.map_id, body.name, body.target.x, body.target.y, body.target.yaw, dock_id),
        )
        row = db.execute("SELECT * FROM dock_stations WHERE id = ?", (dock_id,)).fetchone()
    return _row_to_dock(row)


@router.delete("/{dock_id}")
def delete_dock(dock_id: int):
    with get_db() as db:
        row = db.execute("SELECT id FROM dock_stations WHERE id = ?", (dock_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Dock station not found")
        db.execute("DELETE FROM dock_stations WHERE id = ?", (dock_id,))
    return {"ok": True}
