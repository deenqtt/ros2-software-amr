-- migrate: foreign-keys-off
--
-- Station types as master_control has them: home, pick_drop, charging.
--
-- master_control's Station_t is HOME_STATION=0, PICKDROP_STATION=1,
-- CHARGING_STATION=2, and that is what /station_config's `type` carries. The
-- registry had pick, drop, pick_drop and charging numbered 0..3, so a pick
-- station arrived as a home station and a charging one as a number master_control
-- does not have.
--
-- What happens at a station (pick, drop, drop then pick) is the mission step's
-- task, not the station's type. Every pick and drop station becomes pick_drop;
-- charging stays. This cannot be undone: pick and drop are no longer told apart.
--
-- SQLite cannot alter a CHECK constraint, so stations is rebuilt. mission_steps
-- references it by id, and every id is copied; the runner turns foreign keys off
-- for this file and checks every reference before committing (see
-- FOREIGN_KEYS_OFF in db.py).

CREATE TABLE stations_new (
    id       TEXT PRIMARY KEY,

    -- CASCADE, because a station without its map is a coordinate with no frame
    -- to be measured in. Deleting a map already refuses while a robot is
    -- assigned to it, so this cannot fire on a map anything is running.
    map_id   TEXT NOT NULL REFERENCES maps(id) ON DELETE CASCADE,

    name     TEXT NOT NULL,

    -- Stored as text rather than the wire enum. master_control's Station_t
    -- uses 0=Home, 1=Pick-drop, 2=Charging; that numbering is a transport
    -- detail, and a registry that stores `2` is one nobody can read.
    type     TEXT NOT NULL,

    -- Metres and radians in the map frame, as Nav2 expects them.
    x        REAL NOT NULL,
    y        REAL NOT NULL,

    -- Approach heading. A dock reached from the wrong side is not reached.
    yaw      REAL NOT NULL,

    note     TEXT,

    -- Which robot's pose was captured, when the station was taught by driving
    -- there. NULL for one placed by clicking the map. SET NULL rather than
    -- CASCADE: retiring a robot must not delete the stations it recorded.
    taught_by_robot_id TEXT REFERENCES robots(id) ON DELETE SET NULL,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT stations_name_not_blank CHECK (length(trim(name)) > 0),
    CONSTRAINT stations_type_known CHECK (type IN ('home', 'pick_drop', 'charging'))
);

INSERT INTO stations_new (
    id, map_id, name, type, x, y, yaw, note, taught_by_robot_id, created_at, updated_at
)
SELECT
    id, map_id, name,
    CASE WHEN type IN ('pick', 'drop') THEN 'pick_drop' ELSE type END,
    x, y, yaw, note, taught_by_robot_id, created_at, updated_at
FROM stations;

DROP TABLE stations;
ALTER TABLE stations_new RENAME TO stations;

CREATE UNIQUE INDEX stations_map_name_unique ON stations (map_id, name COLLATE NOCASE);

CREATE INDEX stations_map_idx ON stations (map_id);

CREATE TRIGGER stations_touch_updated_at
AFTER UPDATE ON stations
FOR EACH ROW
BEGIN
    UPDATE stations SET updated_at = datetime('now') WHERE id = NEW.id;
END;
