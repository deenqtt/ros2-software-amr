"""
AMR Backend — FastAPI app entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

from database import init_db, MAPS_DIR
from routers import maps, missions, keepout, docks, destinations, mode

app = FastAPI(title="AMR Backend", version="1.0.0")

# CORS — allow web UI from any origin (same LAN / localhost dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(maps.router)
app.include_router(missions.router)
app.include_router(keepout.router)
app.include_router(docks.router)
app.include_router(destinations.router)
app.include_router(mode.router)

# Serve static map files (.yaml, .pgm, .png)
os.makedirs(MAPS_DIR, exist_ok=True)
app.mount("/maps", StaticFiles(directory=MAPS_DIR), name="maps")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats")
def system_stats():
    """Return basic system stats for the UI footer. Requires psutil (optional)."""
    if _psutil is None:
        return {"cpu_percent": None, "mem_mb": None, "latency_ms": None}
    mem = _psutil.virtual_memory()
    return {
        "cpu_percent": _psutil.cpu_percent(interval=None),
        "mem_mb": round(mem.used / 1024 / 1024),
        "latency_ms": None,   # filled by frontend via ROS ping
    }
