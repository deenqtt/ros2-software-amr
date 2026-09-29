-- What a robot is *supposed* to be doing.
--
-- Until now the mode lived only in the agent's memory and /robot_mode was a
-- command, not a state. Nothing recorded intent, so nothing could restore it: an
-- agent that restarted came back idle and no part of the system noticed, and a
-- robot needed a person to press "start navigation" before it would work at all.
--
-- With this, the registry holds the intent and the agent reconciles towards it —
-- the same arrangement `active_map_id` already uses. Assigning a map is enough
-- to put a robot to work; there is no button in the production flow.
--
--   nav   the resting state. Nav2 up, waiting for goals.
--   map   surveying. SLAM and Nav2 both own /map, so they cannot both run.
--   idle  parked, or being worked on. A choice, not a failure.
--
-- Defaults to 'nav' — including for the robots already registered, which is
-- correct: a robot in a warehouse that is powered on should be ready for work.
-- Nav2 running is not the robot moving; an idle planner plans nothing, and the
-- robot only moves when a mission gives it a goal.

ALTER TABLE robots ADD COLUMN desired_mode TEXT NOT NULL DEFAULT 'nav';

-- A separate index rather than a CHECK on the column: SQLite cannot add a
-- CHECK constraint to an existing table without rewriting it, and the value is
-- validated by the API before it ever reaches here.
CREATE INDEX robots_desired_mode_idx ON robots (desired_mode);
