-- migrate: foreign-keys-off
--
-- A fourth role, and passwords that must be replaced.
--
--   viewer       sees the fleet, maps and history
--   operator     + runs and stops missions, switches robot mode
--   admin        + edits maps, stations, zones, missions and robots
--   super_admin  + manages people and reads the audit trail
--
-- Admin and super admin are split because they are different jobs: the person
-- who redraws a keep-out zone is not usually the person who decides who may
-- sign in, and a mistake in one should not hand out the other.
--
-- must_change_password marks a password someone else chose — the bootstrap
-- account from .env, a new account, an admin reset. Until it is replaced the
-- account can do nothing but replace it.
--
-- SQLite cannot alter a CHECK constraint, so users is rebuilt. Sessions and
-- audit records point at it; the runner turns foreign keys off for this file
-- and checks every reference before committing (see FOREIGN_KEYS_OFF in db.py).

CREATE TABLE users_new (
    id                   TEXT PRIMARY KEY,
    username             TEXT NOT NULL,
    display_name         TEXT,
    role                 TEXT NOT NULL,
    password_hash        TEXT NOT NULL,
    disabled             INTEGER NOT NULL DEFAULT 0,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at        TEXT,

    CONSTRAINT users_role_known CHECK (role IN ('viewer', 'operator', 'admin', 'super_admin')),
    CONSTRAINT users_disabled_bool CHECK (disabled IN (0, 1)),
    CONSTRAINT users_must_change_bool CHECK (must_change_password IN (0, 1)),
    CONSTRAINT users_username_not_blank CHECK (length(trim(username)) > 0)
);

-- Everyone who managed accounts before this still can: every existing admin
-- becomes a super admin. Nobody is locked out of the Users screen by upgrading.
INSERT INTO users_new (
    id, username, display_name, role, password_hash, disabled,
    created_at, updated_at, last_login_at
)
SELECT
    id, username, display_name,
    CASE role WHEN 'admin' THEN 'super_admin' ELSE role END,
    password_hash, disabled, created_at, updated_at, last_login_at
FROM users;

DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

CREATE UNIQUE INDEX users_username_unique ON users (username COLLATE NOCASE);

CREATE TRIGGER users_touch_updated_at
AFTER UPDATE OF username, display_name, role, password_hash, disabled ON users
FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = datetime('now') WHERE id = NEW.id;
END;
