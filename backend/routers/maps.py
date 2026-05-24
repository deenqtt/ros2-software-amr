"""
Maps router — scan filesystem, activate, delete from DB.

Maps are placed manually by engineers into MAPS_DIR.
GET /api/maps scans the folder and auto-registers new .yaml files into the DB.
"""
import os
import shutil
import yaml

from fastapi import APIRouter, HTTPException, UploadFile, File

from database import get_db, MAPS_DIR, ROS_MAPS_PATH
from models import MapOut, MapActivateOut

router = APIRouter(prefix="/api/maps", tags=["maps"])


def _parse_yaml_meta(yaml_path: str) -> dict:
    """Parse a map .yaml file and return metadata dict."""
    meta = {}
    try:
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        meta["resolution"] = data.get("resolution")
        origin = data.get("origin", [0, 0, 0])
        meta["origin_x"] = origin[0] if len(origin) > 0 else 0
        meta["origin_y"] = origin[1] if len(origin) > 1 else 0
        meta["pgm_file"] = data.get("image", "")
    except Exception:
        pass
    return meta


def _read_pgm_size(pgm_path: str) -> tuple[int, int]:
    """Return (width, height) from a PGM header."""
    try:
        with open(pgm_path, "rb") as f:
            def next_token():
                tok = b""
                while True:
                    ch = f.read(1)
                    if not ch:
                        break
                    if ch == b"#":
                        f.readline()
                        continue
                    if ch in (b" ", b"\t", b"\n", b"\r"):
                        if tok:
                            return tok.decode()
                        continue
                    tok += ch
                return tok.decode() if tok else ""

            magic = next_token()
            if magic not in ("P5", "P2"):
                return (None, None)
            w = int(next_token())
            h = int(next_token())
            return (w, h)
    except Exception:
        return (None, None)


def _scan_and_sync(db):
    """
    Scan MAPS_DIR for .yaml files.
    - Insert new ones into DB.
    - Remove DB entries whose file no longer exists.
    Returns list of rows.
    """
    yaml_files = sorted(
        f for f in os.listdir(MAPS_DIR) if f.endswith(".yaml")
    ) if os.path.isdir(MAPS_DIR) else []

    # Remove stale DB entries
    existing = db.execute("SELECT id, yaml_file FROM maps").fetchall()
    for row in existing:
        if row["yaml_file"] not in yaml_files:
            db.execute("DELETE FROM maps WHERE id = ?", (row["id"],))

    # Insert new files
    registered = {r["yaml_file"] for r in db.execute("SELECT yaml_file FROM maps").fetchall()}
    for fname in yaml_files:
        if fname in registered:
            continue
        yaml_path = os.path.join(MAPS_DIR, fname)
        meta = _parse_yaml_meta(yaml_path)
        pgm_name = meta.get("pgm_file") or fname.replace(".yaml", ".pgm")
        pgm_path = os.path.join(MAPS_DIR, pgm_name)
        width, height = _read_pgm_size(pgm_path)
        # Use filename stem as default name
        name = fname.replace(".yaml", "").replace("_", " ").title()
        db.execute(
            """INSERT INTO maps (name, yaml_file, resolution, width, height, origin_x, origin_y)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, fname, meta.get("resolution"), width, height,
             meta.get("origin_x"), meta.get("origin_y")),
        )

    return db.execute("SELECT * FROM maps ORDER BY name").fetchall()


def _row_to_map(row) -> MapOut:
    return MapOut(
        id=row["id"],
        name=row["name"],
        yaml_file=row["yaml_file"],
        resolution=row["resolution"],
        width=row["width"],
        height=row["height"],
        origin_x=row["origin_x"],
        origin_y=row["origin_y"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[MapOut])
def list_maps():
    with get_db() as db:
        rows = _scan_and_sync(db)
    return [_row_to_map(r) for r in rows]


@router.post("/{map_id}/activate", response_model=MapActivateOut)
def activate_map(map_id: int):
    with get_db() as db:
        row = db.execute("SELECT * FROM maps WHERE id = ?", (map_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Map not found")
    # Return path as seen by the ROS container
    yaml_path = os.path.join(ROS_MAPS_PATH, row["yaml_file"])
    return MapActivateOut(yaml_path=yaml_path)


@router.post("/upload", response_model=MapOut)
async def upload_map(
    yaml_file: UploadFile = File(...),
    pgm_file:  UploadFile = File(...),
):
    """
    Upload a map pair (.yaml + .pgm/.png) from the UI.
    Both files are saved to MAPS_DIR and auto-registered into the DB.
    """
    # Validate extensions
    if not yaml_file.filename.endswith(".yaml"):
        raise HTTPException(400, "yaml_file must be a .yaml file")
    if not (pgm_file.filename.endswith(".pgm") or pgm_file.filename.endswith(".png")):
        raise HTTPException(400, "pgm_file must be a .pgm or .png file")

    # Reject path traversal
    yaml_name = os.path.basename(yaml_file.filename)
    pgm_name  = os.path.basename(pgm_file.filename)

    yaml_dest = os.path.join(MAPS_DIR, yaml_name)
    pgm_dest  = os.path.join(MAPS_DIR, pgm_name)

    # Save files to disk
    os.makedirs(MAPS_DIR, exist_ok=True)
    with open(yaml_dest, "wb") as f:
        shutil.copyfileobj(yaml_file.file, f)
    with open(pgm_dest, "wb") as f:
        shutil.copyfileobj(pgm_file.file, f)

    # Re-sync DB and return the newly registered map
    with get_db() as db:
        rows = _scan_and_sync(db)
        row = db.execute(
            "SELECT * FROM maps WHERE yaml_file = ?", (yaml_name,)
        ).fetchone()

    if not row:
        raise HTTPException(500, "Map uploaded but failed to register in DB")

    return _row_to_map(row)


@router.delete("/{map_id}")
def delete_map(map_id: int):
    """Remove map from DB only — files stay on disk (managed by engineer)."""
    with get_db() as db:
        row = db.execute("SELECT id FROM maps WHERE id = ?", (map_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Map not found")
        db.execute("DELETE FROM maps WHERE id = ?", (map_id,))
    return {"ok": True}
