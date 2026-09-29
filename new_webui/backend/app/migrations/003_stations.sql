-- Stations: named poses a robot can be sent to.
--
-- A station belongs to a MAP, not to a robot. Its coordinates are expressed in
-- that map's frame, so the same numbers name a different physical place in any
-- other map. Two robots working the same site share its stations because they
-- share its map.
--
-- The robot side currently keeps stations in a Python dict that is lost on every
-- restart (mission_manager_node.py, `self._stations = {}`). This table is the
-- registry; the robot holds a copy, the same arrangement maps already use.
--
-- Bound to a specific map version, not to the name. A pixel edit leaves origin
-- and resolution alone so coordinates survive it, but a fresh survey of the same
-- site produces a new origin — and stations carried across that would point at
-- the wrong shelves while looking perfectly valid.

CREATE TABLE stations (
    id       TEXT PRIMARY KEY,

    -- CASCADE, because a station without its map is a coordinate with no frame
    -- to be measured in. Deleting a map already refuses while a robot is
    -- assigned to it, so this cannot fire on a map anything is running.
    map_id   TEXT NOT NULL REFERENCES maps(id) ON DELETE CASCADE,

    name     TEXT NOT NULL,

    -- Stored as text rather than the wire enum. The robot's StationConfig.srv
    -- uses 0=Pick, 1=Drop, 2=Pick&Drop, 3=Charging; that numbering is a
    -- transport detail, and a registry that stores `2` is one nobody can read.
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
    CONSTRAINT stations_type_known CHECK (type IN ('pick', 'drop', 'pick_drop', 'charging'))
);

-- A mission step names a station by name, so two stations called "Dock 1" on one
-- map would make a mission ambiguous.
CREATE UNIQUE INDEX stations_map_name_unique ON stations (map_id, name COLLATE NOCASE);

CREATE INDEX stations_map_idx ON stations (map_id);

CREATE TRIGGER stations_touch_updated_at
AFTER UPDATE ON stations
FOR EACH ROW
BEGIN
    UPDATE stations SET updated_at = datetime('now') WHERE id = NEW.id;
END;
