-- What the robot says it is doing, in the unified status vocabulary.
--
-- Until now every surface translated the robot's raw signals for itself:
-- master_control's robot_current_sts codes, the agent's mode/state pair, the
-- run states, the kiosk's phases — and the translations disagreed (code 2
-- means "waiting for the operator's OK"; the web called it "Docking"). The
-- agent now derives one word (see amr_agent/robot_status.py) and reports it
-- here, on change and as a heartbeat, so the dashboard, the robot page and
-- the mission list all read the same registry row instead of re-translating.
--
--   parked / mapping / ready / on_mission / waiting_confirm / charging /
--   error / paused
--
-- status is NULL until the agent's first report: a robot that has never
-- spoken has no status, rather than a made-up one. `offline` is never stored
-- on the robot's behalf — the reader decides it from the age of
-- status_reported_at, because only the robot could know it stopped.
--
-- status_since moves only when the status itself changes, so "on mission for
-- 4 minutes" survives the heartbeat; status_reported_at moves on every
-- report, and its age is the liveness signal.

ALTER TABLE robots ADD COLUMN status TEXT;
ALTER TABLE robots ADD COLUMN status_detail TEXT NOT NULL DEFAULT '';
ALTER TABLE robots ADD COLUMN status_since TEXT;
ALTER TABLE robots ADD COLUMN status_reported_at TEXT;

-- The value is validated by the API against the vocabulary before it reaches
-- here, and the vocabulary is expected to grow (paused has no control yet);
-- a CHECK constraint would rewrite the table on every new word.
CREATE INDEX robots_status_idx ON robots (status);
