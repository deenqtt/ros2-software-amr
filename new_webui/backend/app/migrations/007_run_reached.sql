-- The last stop a run actually arrived at.
--
-- `step_index` is the step the robot is *on*: the agent writes it before it
-- sets off, so it cannot say "arrived". The UI had to infer arrival from the
-- index moving on, which happens only when the next step starts — and never
-- for the last step of a lap. A notification built on that inference is late
-- for every stop and silent for the last one.
--
-- These are written by the agent the moment Nav2 reports success:
--
--   reached_lap    the lap it was on
--   reached_index  the step it reached, from 0 like step_index
--   reached_at     stamped by the server, so a repeat of the same step on the
--                  next lap is still a new arrival and not a duplicate
--
-- Nullable: a run that has not reached anything yet has not.

ALTER TABLE mission_runs ADD COLUMN reached_lap INTEGER;
ALTER TABLE mission_runs ADD COLUMN reached_index INTEGER;
ALTER TABLE mission_runs ADD COLUMN reached_at TEXT;
