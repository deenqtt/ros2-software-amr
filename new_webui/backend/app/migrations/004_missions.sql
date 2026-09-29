-- Missions: an ordered route, and the record of running one.
--
-- Two tables, because they are two different things and conflating them is what
-- the old design did. A *mission* is a route: "Pickup A, then Dropoff". A *run*
-- is one execution of it by one robot, at a lap and a step. The route changes
-- when somebody edits it; the run changes every few seconds.
--
-- Looping lives on the run, not on the mission. The same route is sometimes a
-- one-off delivery and sometimes a shift of shuttling, and putting `loop` on the
-- route forces two near-identical missions that drift apart the moment one is
-- edited. The old schema had `loop` and `loop_count` on `missions`.
--
-- One step maps exactly onto one custom_interfaces/action/MissionPlan goal, so
-- nothing in the ROS contract has to change: the agent sends one goal per step
-- and advances when it completes.

CREATE TABLE missions (
    id       TEXT PRIMARY KEY,

    -- A mission names stations, and a station's coordinates only mean anything
    -- in one map's frame. RESTRICT rather than CASCADE: deleting a map should
    -- not silently take every route written against it.
    map_id   TEXT NOT NULL REFERENCES maps(id) ON DELETE RESTRICT,

    name     TEXT NOT NULL,
    note     TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT missions_name_not_blank CHECK (length(trim(name)) > 0)
);

CREATE UNIQUE INDEX missions_map_name_unique ON missions (map_id, name COLLATE NOCASE);
CREATE INDEX missions_map_idx ON missions (map_id);

CREATE TABLE mission_steps (
    id          TEXT PRIMARY KEY,
    mission_id  TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,

    -- Position in the route, from 1. Holes are allowed while a reorder is in
    -- flight; only the order matters, not the values.
    ordinal     INTEGER NOT NULL,

    -- RESTRICT: a step pointing at a station that no longer exists fails on the
    -- robot with "Unknown station_id", in front of whoever is standing there.
    -- Deleting a station a mission uses is refused and names the missions.
    station_id  TEXT NOT NULL REFERENCES stations(id) ON DELETE RESTRICT,

    -- What to do on arrival. MissionPlan.action carries 1=Pick, 2=Drop; `none`
    -- is a waypoint the robot merely passes through. The wire value is derived
    -- at the edge, so the registry stays readable.
    task        TEXT NOT NULL,

    -- MissionPlan.continue_mode inverted into something readable: `auto`
    -- continues by itself, `confirm` waits for /mission_confirm — someone has
    -- to be standing there to press it.
    confirm     TEXT NOT NULL DEFAULT 'auto',

    note        TEXT,

    CONSTRAINT mission_steps_task_known CHECK (task IN ('none', 'pick', 'drop')),
    CONSTRAINT mission_steps_confirm_known CHECK (confirm IN ('auto', 'confirm')),
    CONSTRAINT mission_steps_ordinal_positive CHECK (ordinal > 0)
);

CREATE UNIQUE INDEX mission_steps_order_unique ON mission_steps (mission_id, ordinal);
CREATE INDEX mission_steps_mission_idx ON mission_steps (mission_id);
CREATE INDEX mission_steps_station_idx ON mission_steps (station_id);

-- One execution of one mission by one robot.
CREATE TABLE mission_runs (
    id          TEXT PRIMARY KEY,

    -- SET NULL, not CASCADE: the history of what a robot did must survive the
    -- route being deleted. `mission_name` keeps it readable afterwards.
    mission_id  TEXT REFERENCES missions(id) ON DELETE SET NULL,
    mission_name TEXT NOT NULL,

    robot_id    TEXT REFERENCES robots(id) ON DELETE SET NULL,

    -- once   : one pass
    -- laps   : laps_target passes
    -- forever: until stopped
    mode        TEXT NOT NULL,
    laps_target INTEGER,

    -- Progress, owned by the robot's agent and written back here. The browser
    -- used to hold these in tab memory, so a refresh mid-mission lost the count
    -- while the robot kept driving.
    lap         INTEGER NOT NULL DEFAULT 1,
    step_index  INTEGER NOT NULL DEFAULT 0,

    -- running  : executing
    -- stopping : finish the current lap, then stop
    -- done / failed / canceled : terminal
    state       TEXT NOT NULL DEFAULT 'running',
    detail      TEXT,

    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at    TEXT,

    CONSTRAINT mission_runs_mode_known CHECK (mode IN ('once', 'laps', 'forever')),
    CONSTRAINT mission_runs_state_known
        CHECK (state IN ('running', 'stopping', 'done', 'failed', 'canceled')),
    -- `laps` without a count is not a number of laps.
    CONSTRAINT mission_runs_laps_target CHECK (
        (mode = 'laps' AND laps_target > 0) OR (mode <> 'laps' AND laps_target IS NULL)
    )
);

-- One live run per robot, enforced here rather than by a check in a handler.
--
-- This is the "no queue" decision made structural: dispatching to a busy robot
-- is refused. A mission is already an ordered list, so "do A then B" is one
-- mission rather than two queued ones, and a scheduler would mostly duplicate
-- what a mission does. Adding a queue later means allowing a `queued` state,
-- not reshaping this.
CREATE UNIQUE INDEX mission_runs_one_live_per_robot
    ON mission_runs (robot_id)
    WHERE state IN ('running', 'stopping');

CREATE INDEX mission_runs_mission_idx ON mission_runs (mission_id);
CREATE INDEX mission_runs_state_idx ON mission_runs (state);

CREATE TRIGGER missions_touch_updated_at
AFTER UPDATE ON missions
FOR EACH ROW
BEGIN
    UPDATE missions SET updated_at = datetime('now') WHERE id = NEW.id;
END;
