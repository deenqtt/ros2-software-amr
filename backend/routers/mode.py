"""
Mode router — switch AMR antara SLAM (mapping) dan Navigation mode.
Mode disimpan ke DB supaya survive backend restart.
"""
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db

router = APIRouter(prefix="/api/mode", tags=["mode"])

SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "docker_run.sh"


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

    if not SCRIPT.exists():
        raise HTTPException(status_code=500, detail=f"Script tidak ditemukan: {SCRIPT}")

    if req.mode == "slam":
        cmd = ["bash", str(SCRIPT), "slam"]
        label = "Mapping (SLAM)"
        map_file = ""
    else:
        map_file = req.map_file or "/maps/amr_map.yaml"
        cmd = ["bash", str(SCRIPT), "nav", map_file]
        label = f"Navigation (map: {map_file})"

    def _run():
        try:
            subprocess.run(["bash", str(SCRIPT), "down"], check=False, capture_output=True)
            subprocess.run(cmd, check=False, capture_output=True)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()

    # Persist ke DB — survive backend restart
    _save_mode(req.mode, map_file)

    return SwitchResponse(
        mode=req.mode,
        map_file=map_file,
        message=f"Switching ke {label}...",
    )
