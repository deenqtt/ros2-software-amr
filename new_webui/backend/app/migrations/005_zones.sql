-- Zones: areas of a map that change how a robot behaves inside them.
--
-- Not just keepout. Nav2 enforces zones through *costmap filters*, of which
-- there are exactly three kinds, and this table covers all of them:
--
--   keepout  -> KeepoutFilter, mask value 100. Never enter.
--   avoid    -> KeepoutFilter, mask value 1..99. Go around if you reasonably
--               can. Same filter as keepout; only the mask value differs, which
--               is why they share a row shape.
--   speed    -> SpeedFilter, a maximum velocity in m/s.
--   binary   -> BinaryFilter, toggles a topic on entry. A beacon, a buzzer, a
--               camera that must be off in a particular room.
--
-- Stored as polygons, never as the mask image. A mask is tied to one map's
-- resolution and cannot be edited back into corners; the polygon is the thing
-- an operator drew, and the mask is derived from it when it is pushed to a
-- robot. The previous backend had this right.
--
-- A zone belongs to a MAP, not to a robot: a speed limit at a blind corner is a
-- property of the building. A robot that must go slower everywhere is a robot
-- setting, not a zone.
--
-- What is deliberately absent: one-way lanes, single-robot zones, stop signs.
-- Those need an arbiter that knows where every robot is, and a costmap filter
-- is an image read by one robot on its own — Nav2 has no concept of the others.

CREATE TABLE zones (
    id       TEXT PRIMARY KEY,

    -- CASCADE, because a polygon without its map is a list of coordinates with
    -- no frame to be measured in.
    map_id   TEXT NOT NULL REFERENCES maps(id) ON DELETE CASCADE,

    name     TEXT NOT NULL,
    kind     TEXT NOT NULL,

    -- JSON array of [x, y] pairs, metres in the map frame. Metres and not
    -- pixels: a re-survey at a finer resolution must not move a zone.
    polygon  TEXT NOT NULL,

    -- Exactly one of these applies, decided by `kind`, and the CHECKs below
    -- refuse the combinations that would be meaningless — a speed limit on a
    -- keepout zone is a number nobody reads.
    speed_limit REAL,     -- m/s, kind = 'speed'
    avoid_cost  INTEGER,  -- 1..99 reluctance, kind = 'avoid'

    -- Switched off without being deleted. A zone put up for a fortnight of
    -- building work should come back the same shape, not be redrawn by eye.
    enabled  INTEGER NOT NULL DEFAULT 1,

    note     TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT zones_name_not_blank CHECK (length(trim(name)) > 0),
    CONSTRAINT zones_kind_known CHECK (kind IN ('keepout', 'avoid', 'speed', 'binary')),

    CONSTRAINT zones_speed_limit_belongs_to_speed CHECK (
        (kind = 'speed' AND speed_limit > 0) OR (kind <> 'speed' AND speed_limit IS NULL)
    ),
    -- 100 would be a keepout, and 0 would be no reluctance at all.
    CONSTRAINT zones_avoid_cost_belongs_to_avoid CHECK (
        (kind = 'avoid' AND avoid_cost BETWEEN 1 AND 99)
        OR (kind <> 'avoid' AND avoid_cost IS NULL)
    )
);

-- A zone is named in logs and on screen, so two with one name on one map would
-- make "slow zone is active" ambiguous.
CREATE UNIQUE INDEX zones_map_name_unique ON zones (map_id, name COLLATE NOCASE);

CREATE INDEX zones_map_idx ON zones (map_id);
CREATE INDEX zones_kind_idx ON zones (kind);

CREATE TRIGGER zones_touch_updated_at
AFTER UPDATE ON zones
FOR EACH ROW
BEGIN
    UPDATE zones SET updated_at = datetime('now') WHERE id = NEW.id;
END;
