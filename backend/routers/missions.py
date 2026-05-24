"""
Missions router — CRUD backed by SQLite.
"""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from models import MissionIn, MissionOut, WaypointItem

router = APIRouter(prefix="/api/missions", tags=["missions"])


def _row_to_mission(row) -> MissionOut:
    return MissionOut(
        id=row["id"],
        name=row["name"],
        map_id=row["map_id"],
        waypoints=[WaypointItem(**w) for w in json.loads(row["waypoints"])],
        loop=bool(row["loop"]),
        loop_count=row["loop_count"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[MissionOut])
def list_missions(map_id: Optional[int] = Query(None)):
    with get_db() as db:
        if map_id is not None:
            rows = db.execute(
                "SELECT * FROM missions WHERE map_id = ? ORDER BY created_at DESC", (map_id,)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM missions ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_mission(r) for r in rows]


@router.post("", response_model=MissionOut)
def create_mission(body: MissionIn):
    wp_json = json.dumps([w.model_dump() for w in body.waypoints])
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO missions (name, map_id, waypoints, loop, loop_count) VALUES (?, ?, ?, ?, ?)",
            (body.name, body.map_id, wp_json, int(body.loop), body.loop_count),
        )
        row = db.execute("SELECT * FROM missions WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_mission(row)


@router.put("/{mission_id}", response_model=MissionOut)
def update_mission(mission_id: int, body: MissionIn):
    wp_json = json.dumps([w.model_dump() for w in body.waypoints])
    with get_db() as db:
        row = db.execute("SELECT id FROM missions WHERE id = ?", (mission_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Mission not found")
        db.execute(
            "UPDATE missions SET name=?, map_id=?, waypoints=?, loop=?, loop_count=? WHERE id=?",
            (body.name, body.map_id, wp_json, int(body.loop), body.loop_count, mission_id),
        )
        row = db.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)).fetchone()
    return _row_to_mission(row)


@router.delete("/{mission_id}")
def delete_mission(mission_id: int):
    with get_db() as db:
        row = db.execute("SELECT id FROM missions WHERE id = ?", (mission_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Mission not found")
        db.execute("DELETE FROM missions WHERE id = ?", (mission_id,))
    return {"ok": True}
