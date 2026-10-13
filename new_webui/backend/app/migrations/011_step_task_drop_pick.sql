-- migrate: foreign-keys-off
--
-- A fourth step task: drop_pick, take the carried item off and put a new one
-- on at the same station.
--
-- master_control already knows it (Station_Action_t DROP_PICK = 3 on
-- MissionPlan.dest_tasks); the registry could not say it. Every existing step
-- is copied unchanged.
--
-- SQLite cannot alter a CHECK constraint, so mission_steps is rebuilt. Nothing
-- references it, but it references missions and stations; the runner turns
-- foreign keys off for this file and checks every reference before committing
-- (see FOREIGN_KEYS_OFF in db.py).

CREATE TABLE mission_steps_new (
    id          TEXT PRIMARY KEY,
    mission_id  TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,

    -- Position in the route, from 1. Holes are allowed while a reorder is in
    -- flight; only the order matters, not the values.
    ordinal     INTEGER NOT NULL,

    -- RESTRICT: a step pointing at a station that no longer exists fails on the
    -- robot with "Unknown station_id", in front of whoever is standing there.
    -- Deleting a station a mission uses is refused and names the missions.
    station_id  TEXT NOT NULL REFERENCES stations(id) ON DELETE RESTRICT,

    -- What to do on arrival. MissionPlan.action carries 1=Pick, 2=Drop,
    -- 3=Drop then pick; `none` is a waypoint the robot merely passes through.
    -- The wire value is derived at the edge, so the registry stays readable.
    task        TEXT NOT NULL,

    -- MissionPlan.continue_mode inverted into something readable: `auto`
    -- continues by itself, `confirm` waits for /mission_confirm — someone has
    -- to be standing there to press it.
    confirm     TEXT NOT NULL DEFAULT 'auto',

    note        TEXT,

    CONSTRAINT mission_steps_task_known CHECK (task IN ('none', 'pick', 'drop', 'drop_pick')),
    CONSTRAINT mission_steps_confirm_known CHECK (confirm IN ('auto', 'confirm')),
    CONSTRAINT mission_steps_ordinal_positive CHECK (ordinal > 0)
);

INSERT INTO mission_steps_new (id, mission_id, ordinal, station_id, task, confirm, note)
SELECT id, mission_id, ordinal, station_id, task, confirm, note
FROM mission_steps;

DROP TABLE mission_steps;
ALTER TABLE mission_steps_new RENAME TO mission_steps;

CREATE UNIQUE INDEX mission_steps_order_unique ON mission_steps (mission_id, ordinal);
CREATE INDEX mission_steps_mission_idx ON mission_steps (mission_id);
CREATE INDEX mission_steps_station_idx ON mission_steps (station_id);
