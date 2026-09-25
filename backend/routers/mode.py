"""
Mode router — switch AMR antara SLAM (mapping) dan Navigation mode.
Mode disimpan ke DB supaya survive backend restart.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db

router = APIRouter(prefix="/api/mode", tags=["mode"])

class SwitchRequest(BaseModel):
    mode: str           # "slam" | "navigation"
    map_file: str = ""  # opsional, hanya dipakai kalau mode=navigation


class SwitchResponse(BaseModel):
    mode: str
    map_file: str
    message: str


def _get_persisted_mode() -> dict:
    with get_db() as db:
        rows = db.execute(
            "SELECT key, value FROM settings WHERE key IN ('ros_mode', 'ros_map_file')"
        ).fetchall()
    data = {r["key"]: r["value"] for r in rows}
    return {
        "mode": data.get("ros_mode", "navigation"),
        "map_file": data.get("ros_map_file", ""),
    }


def _save_mode(mode: str, map_file: str = ""):
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ros_mode', ?)", (mode,))
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ros_map_file', ?)", (map_file,))


@router.get("", response_model=dict)
def get_mode():
    return _get_persisted_mode()


@router.post("/switch", response_model=SwitchResponse)
def switch_mode(req: SwitchRequest):
    if req.mode not in ("slam", "navigation"):
        raise HTTPException(status_code=400, detail="mode harus 'slam' atau 'navigation'")

    if req.mode == "slam":
        label = "Mapping (SLAM)"
        map_file = ""
    else:
        map_file = req.map_file or "/maps/amr_map.yaml"
        label = f"Navigation (map: {map_file})"

    # Persist ke DB — survive backend restart
    _save_mode(req.mode, map_file)

    return SwitchResponse(
        mode=req.mode,
        map_file=map_file,
        message=(
            f"{label} disimpan. Jalankan command runtime di terminal host: "
            f"bash scripts/docker_run.sh {'slam' if req.mode == 'slam' else f'nav {map_file}'}"
        ),
    )
