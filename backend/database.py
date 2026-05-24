"""
SQLite database setup for AMR backend.
"""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "/data/amr.db")
MAPS_DIR = os.environ.get("MAPS_DIR", "/maps")
# Path ke maps folder sebagaimana dilihat oleh container ROS (amr-sim)
# Di Docker: /maps (keduanya mount ./maps:/maps)
# Di local dev: path absolut ke folder maps di host
ROS_MAPS_PATH = os.environ.get("ROS_MAPS_PATH", MAPS_DIR)


def init_db():
    os.makedirs(MAPS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS maps (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            yaml_file   TEXT    NOT NULL UNIQUE,
            resolution  REAL,
            width       INTEGER,
            height      INTEGER,
            origin_x    REAL,
            origin_y    REAL,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS missions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            map_id      INTEGER REFERENCES maps(id) ON DELETE SET NULL,
            waypoints   TEXT    NOT NULL,
            loop        INTEGER DEFAULT 0,
            loop_count  INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS keepout_zones (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            map_id  INTEGER NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
            name    TEXT    NOT NULL,
            polygon TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dock_stations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            map_id        INTEGER REFERENCES maps(id) ON DELETE CASCADE,
            name          TEXT    NOT NULL,
            x             REAL    NOT NULL,
            y             REAL    NOT NULL,
            theta         REAL    DEFAULT 0,
            approach_x    REAL,
            approach_y    REAL,
            approach_yaw  REAL    DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS destinations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            map_id       INTEGER REFERENCES maps(id) ON DELETE CASCADE,
            name         TEXT    NOT NULL,
            x            REAL    NOT NULL,
            y            REAL    NOT NULL,
            yaw          REAL    DEFAULT 0,
            station_type INTEGER DEFAULT 2,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT OR IGNORE INTO settings (key, value) VALUES ('ros_mode', 'navigation');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('ros_map_file', '');
    """)
    con.commit()
    # Migrate: tambah kolom baru untuk DB lama
    for migration in [
        "ALTER TABLE dock_stations ADD COLUMN approach_yaw REAL DEFAULT 0",
        "ALTER TABLE destinations ADD COLUMN station_type INTEGER DEFAULT 2",
        "ALTER TABLE destinations ADD COLUMN yaw REAL DEFAULT 0",
    ]:
        try:
            con.execute(migration)
            con.commit()
        except Exception:
            pass  # kolom sudah ada
    con.close()


@contextmanager
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
