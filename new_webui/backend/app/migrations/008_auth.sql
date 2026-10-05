-- People, their sessions, and a record of what they changed.
--
-- Until now every endpoint answered anyone who could reach the port: anyone on
-- the plant network could dispatch a robot, delete a map, or redraw a keepout
-- zone, and nothing recorded who had. Fleet managers in this class (MiR Fleet,
-- OTTO Fleet Manager, Omron FLOW) all separate the person who watches, the one
-- who runs the robots, and the one who changes the site — and IEC 62443 asks
-- for exactly that plus an audit trail.
--
-- Three roles, ordered: each can do everything the one before it can.
--
--   viewer    sees the fleet, maps and history
--   operator  + runs and stops missions, switches robot mode
--   admin     + edits maps, stations, zones, missions, robots and people

CREATE TABLE users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL,
    display_name  TEXT,
    role          TEXT NOT NULL,

    -- scrypt, with its parameters and salt in the string, so the cost can be
    -- raised later without a migration: old hashes still say how they were made.
    password_hash TEXT NOT NULL,

    -- Disable rather than delete when someone leaves: their name stays on the
    -- audit records it is attached to, and nobody can sign in as them.
    disabled      INTEGER NOT NULL DEFAULT 0,

    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT,

    CONSTRAINT users_role_known CHECK (role IN ('viewer', 'operator', 'admin')),
    CONSTRAINT users_disabled_bool CHECK (disabled IN (0, 1)),
    CONSTRAINT users_username_not_blank CHECK (length(trim(username)) > 0)
);

-- "Rifai" and "rifai" are one person at a login prompt.
CREATE UNIQUE INDEX users_username_unique ON users (username COLLATE NOCASE);

CREATE TRIGGER users_touch_updated_at
AFTER UPDATE OF username, display_name, role, password_hash, disabled ON users
FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- One row per signed-in browser.
--
-- Only a SHA-256 of the token is stored. The token itself lives in the
-- browser's HttpOnly cookie, so a copy of this database (a backup, a support
-- bundle) cannot be replayed to sign in as anyone.
CREATE TABLE sessions (
    token_hash   TEXT PRIMARY KEY,
    -- CASCADE: deleting a person signs them out everywhere.
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    -- Idle expiry is measured from here. Touched at most once a minute, so a
    -- busy screen does not write on every request.
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    user_agent   TEXT
);

CREATE INDEX sessions_user_idx ON sessions (user_id);
CREATE INDEX sessions_last_seen_idx ON sessions (last_seen_at);

-- Who changed what, and when.
--
-- Written for every change made through the API and for every sign-in attempt.
-- The person is copied in as text rather than only referenced, so the record
-- still reads correctly after their account is renamed or removed.
CREATE TABLE audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    at        TEXT NOT NULL DEFAULT (datetime('now')),

    -- SET NULL: the record outlives the account.
    user_id   TEXT REFERENCES users(id) ON DELETE SET NULL,
    -- The name as typed for a failed sign-in, 'agent' for a robot agent.
    username  TEXT,
    role      TEXT,

    -- What was asked for. The UI turns method + path into words.
    action    TEXT NOT NULL,
    method    TEXT,
    path      TEXT,
    status    INTEGER,
    detail    TEXT,
    ip        TEXT
);

CREATE INDEX audit_log_at_idx ON audit_log (at);
CREATE INDEX audit_log_user_idx ON audit_log (user_id);

-- Who pressed Run. Text, like mission_name, so history survives the account.
ALTER TABLE mission_runs ADD COLUMN started_by TEXT;
