"""
Keepout zones router.
"""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from models import KeepoutIn, KeepoutOut, PointXY

router = APIRouter(prefix="/api/keepout", tags=["keepout"])


def _row_to_keepout(row) -> KeepoutOut:
    return KeepoutOut(
        id=row["id"],
        map_id=row["map_id"],
        name=row["name"],
        polygon=[PointXY(**p) for p in json.loads(row["polygon"])],
    )


@router.get("", response_model=list[KeepoutOut])
def list_keepout(map_id: Optional[int] = Query(None)):
    with get_db() as db:
        if map_id is not None:
            rows = db.execute(
                "SELECT * FROM keepout_zones WHERE map_id = ?", (map_id,)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM keepout_zones").fetchall()
    return [_row_to_keepout(r) for r in rows]


@router.post("", response_model=KeepoutOut)
def create_keepout(body: KeepoutIn):
    poly_json = json.dumps([p.model_dump() for p in body.polygon])
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO keepout_zones (map_id, name, polygon) VALUES (?, ?, ?)",
            (body.map_id, body.name, poly_json),
        )
        row = db.execute("SELECT * FROM keepout_zones WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_keepout(row)


@router.delete("/{zone_id}")
def delete_keepout(zone_id: int):
    with get_db() as db:
        row = db.execute("SELECT id FROM keepout_zones WHERE id = ?", (zone_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Keepout zone not found")
        db.execute("DELETE FROM keepout_zones WHERE id = ?", (zone_id,))
    return {"ok": True}
