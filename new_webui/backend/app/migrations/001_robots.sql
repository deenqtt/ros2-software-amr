-- Robot registry.
--
-- This table is the thing the previous schema never had. There, a robot was an
-- implicit singleton defined by one build-time VITE_ROS_URL in the frontend,
-- and not one of the six tables carried a robot reference. Every screen, every
-- endpoint and every ROS topic name silently assumed exactly one machine.
--
-- Starting from a robots table means the rest of the schema can carry a real
-- foreign key from the first migration, instead of needing a rewrite later.

CREATE TABLE robots (
    -- UUID text rather than an autoincrement integer: registries get merged
    -- across machines, and two sites both holding "robot 3" is a bad day.
    id            TEXT    PRIMARY KEY,
    name          TEXT    NOT NULL,
    bridge_url    TEXT    NOT NULL,

    -- Optional. Only matters when something on the operator's own machine
    -- speaks DDS directly; the browser reaches the robot through rosbridge,
    -- which does not care about the domain. NULL means "not set", which is
    -- distinct from 0 — zero is a valid ROS domain.
    ros_domain_id INTEGER,

    camera_url    TEXT,
    -- Topic namespace. Empty string for the one-bridge-per-robot topology.
    namespace     TEXT    NOT NULL DEFAULT '',
    serial        TEXT,

    -- 1-8, indexes the UI's accent tokens. Identity only, never status: it is
    -- the cue that stops an operator acting on the wrong machine.
    accent        INTEGER NOT NULL DEFAULT 1,

    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT robots_accent_range CHECK (accent BETWEEN 1 AND 8),
    CONSTRAINT robots_domain_range CHECK (
        ros_domain_id IS NULL OR (ros_domain_id BETWEEN 0 AND 232)
    ),
    CONSTRAINT robots_name_not_blank CHECK (length(trim(name)) > 0),
    CONSTRAINT robots_bridge_not_blank CHECK (length(trim(bridge_url)) > 0)
);

-- Two robots sharing a name is how an operator ends up driving the wrong one,
-- so the database refuses it rather than trusting every caller to check.
-- NOCASE, because "AMR-01" and "amr-01" are the same machine to a human.
CREATE UNIQUE INDEX robots_name_unique ON robots (name COLLATE NOCASE);

-- One bridge address serves one robot. Two records pointing at the same
-- rosbridge would show as two robots that move together.
CREATE UNIQUE INDEX robots_bridge_unique ON robots (bridge_url);

CREATE TRIGGER robots_touch_updated_at
AFTER UPDATE ON robots
FOR EACH ROW
BEGIN
    UPDATE robots SET updated_at = datetime('now') WHERE id = NEW.id;
END;
