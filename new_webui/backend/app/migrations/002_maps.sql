-- Map registry.
--
-- The backend is the source of truth for maps; robots keep a local cache and
-- pull when told to. A map is still *born* on the robot — slam_toolbox writes
-- it to the robot's own disk, so mapping succeeds even when the server is
-- unreachable — and is then published here.
--
-- Two rules are enforced by the schema rather than by convention:
--
-- 1. Maps are immutable. Saving the same name again creates a new version
--    instead of overwriting. Stations store coordinates in a specific map
--    frame, so replacing a map's contents silently invalidates every station
--    attached to it, on every robot still running the old one.
--
-- 2. Every map carries a content hash, so "robot B is on map 7" can be
--    verified rather than assumed.

CREATE TABLE maps (
    id            TEXT    PRIMARY KEY,
    -- Human name, shared across versions: "Warehouse A" v1, v2, v3.
    name          TEXT    NOT NULL,
    version       INTEGER NOT NULL,

    -- sha256 of the image bytes. The robot compares this against its cache to
    -- decide whether a download is needed.
    content_hash  TEXT    NOT NULL,

    -- Stored filenames, relative to this map's own directory. Each map gets a
    -- directory named after its id, so two maps called "map.pgm" cannot
    -- collide the way a flat folder allowed.
    yaml_file     TEXT    NOT NULL,
    image_file    TEXT    NOT NULL,
    image_bytes   INTEGER NOT NULL,

    -- Parsed from the yaml on ingest, so the UI can show a map's scale and
    -- extent without downloading the image.
    resolution    REAL,
    width         INTEGER,
    height        INTEGER,
    origin_x      REAL,
    origin_y      REAL,
    origin_yaw    REAL,
    negate        INTEGER,
    occupied_thresh REAL,
    free_thresh   REAL,

    -- Which robot produced it. SET NULL rather than CASCADE: retiring a robot
    -- must not delete the maps it surveyed.
    created_by_robot_id TEXT REFERENCES robots(id) ON DELETE SET NULL,
    note          TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT maps_version_positive CHECK (version > 0),
    CONSTRAINT maps_name_not_blank   CHECK (length(trim(name)) > 0)
);

-- One version number per name. This is what makes "create the next version"
-- safe against two robots saving at the same moment: the second insert fails
-- and is retried rather than silently producing a duplicate.
CREATE UNIQUE INDEX maps_name_version_unique ON maps (name COLLATE NOCASE, version);

CREATE INDEX maps_name_idx ON maps (name COLLATE NOCASE);
CREATE INDEX maps_hash_idx ON maps (content_hash);

-- Which map a robot is meant to be running.
--
-- SET NULL, not CASCADE: deleting a map must never delete a robot. The delete
-- endpoint refuses while any robot still points at it, so reaching this is the
-- last line of defence rather than the normal path.
ALTER TABLE robots ADD COLUMN active_map_id TEXT REFERENCES maps(id) ON DELETE SET NULL;
