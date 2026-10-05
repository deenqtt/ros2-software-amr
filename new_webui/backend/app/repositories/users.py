"""
People and their sessions.

SQL lives here and nowhere else, like the other repositories.
"""

from __future__ import annotations

import sqlite3
import uuid

_USER_COLUMNS = """
    id, username, display_name, role, disabled, must_change_password,
    created_at, updated_at, last_login_at
"""


class DuplicateUserError(Exception):
    """Another account already holds the username."""

    def __init__(self, username: str) -> None:
        super().__init__(f"There is already an account called '{username}'")
        self.username = username


class LastAdminError(Exception):
    """The change would leave nobody able to manage accounts."""

    def __init__(self) -> None:
        super().__init__(
            "This is the only active super admin. Make someone else a super admin "
            "first, or nobody will be able to manage accounts."
        )


# ── Users ─────────────────────────────────────────────────────────────────────


def list_users(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        f"SELECT {_USER_COLUMNS} FROM users ORDER BY username COLLATE NOCASE"  # noqa: S608 — fixed literal
    ).fetchall()


def get_user(connection: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
    return connection.execute(
        f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?",  # noqa: S608 — fixed literal
        (user_id,),
    ).fetchone()


def get_credentials(connection: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    """The row a sign-in checks against, password hash included. Nothing else reads it."""
    return connection.execute(
        f"SELECT {_USER_COLUMNS}, password_hash FROM users "  # noqa: S608 — fixed literal
        "WHERE username = ? COLLATE NOCASE",
        (username,),
    ).fetchone()


def get_password_hash(connection: sqlite3.Connection, user_id: str) -> str | None:
    row = connection.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    return None if row is None else str(row["password_hash"])


def count_users(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT count(*) AS n FROM users").fetchone()["n"])


def count_active_super_admins(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT count(*) AS n FROM users WHERE role = 'super_admin' AND disabled = 0"
    ).fetchone()
    return int(row["n"])


def create_user(connection: sqlite3.Connection, payload: dict) -> sqlite3.Row:
    user_id = payload.get("id") or str(uuid.uuid4())
    try:
        connection.execute(
            """
            INSERT INTO users (
                id, username, display_name, role, password_hash, must_change_password
            ) VALUES (
                :id, :username, :display_name, :role, :password_hash, :must_change_password
            )
            """,
            {"display_name": None, "must_change_password": 0, **payload, "id": user_id},
        )
    except sqlite3.IntegrityError as error:
        if "users.username" in str(error) or "users_username_unique" in str(error):
            raise DuplicateUserError(payload["username"]) from error
        raise
    created = get_user(connection, user_id)
    if created is None:  # pragma: no cover — the insert just succeeded
        raise RuntimeError("user disappeared immediately after insert")
    return created


_UPDATABLE = ("display_name", "role", "disabled", "password_hash", "must_change_password")


def update_user(connection: sqlite3.Connection, user_id: str, patch: dict) -> sqlite3.Row | None:
    """
    Apply a partial update, refusing one that leaves no active super admin.

    The check runs inside the caller's transaction, after the write, so two
    super admins demoting each other at the same moment cannot both succeed.
    """
    fields = {key: value for key, value in patch.items() if key in _UPDATABLE}
    if fields:
        was_super_admin = _is_active_super_admin(connection, user_id)
        assignments = ", ".join(f"{key} = :{key}" for key in fields)
        connection.execute(
            f"UPDATE users SET {assignments} WHERE id = :id",  # noqa: S608 — keys from _UPDATABLE
            {**fields, "id": user_id},
        )
        # Only a change that takes an active super admin away can leave none. Anything
        # else — a password, a name, a non-admin — is fine even on a system
        # that has no super admin yet.
        if was_super_admin and count_active_super_admins(connection) == 0:
            raise LastAdminError
    return get_user(connection, user_id)


def _is_active_super_admin(connection: sqlite3.Connection, user_id: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM users WHERE id = ? AND role = 'super_admin' AND disabled = 0", (user_id,)
    ).fetchone()
    return row is not None


def delete_user(connection: sqlite3.Connection, user_id: str) -> bool:
    was_super_admin = _is_active_super_admin(connection, user_id)
    deleted = connection.execute("DELETE FROM users WHERE id = ?", (user_id,)).rowcount > 0
    if was_super_admin and count_active_super_admins(connection) == 0:
        raise LastAdminError
    return deleted


def mark_login(connection: sqlite3.Connection, user_id: str) -> None:
    connection.execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (user_id,))


# ── Sessions ──────────────────────────────────────────────────────────────────


def create_session(
    connection: sqlite3.Connection, token_hash: str, user_id: str, user_agent: str | None
) -> None:
    connection.execute(
        "INSERT INTO sessions (token_hash, user_id, user_agent) VALUES (?, ?, ?)",
        (token_hash, user_id, (user_agent or "")[:200] or None),
    )


def resolve_session(
    connection: sqlite3.Connection, token_hash: str, idle_minutes: int
) -> sqlite3.Row | None:
    """
    The signed-in user for a token, or None if it is unknown, idle too long, or
    the account has been disabled since.

    Touches the session at most once a minute: often enough for idle expiry to
    be accurate to the minute, rarely enough that a screen polling every second
    does not turn every read into a write.
    """
    row = connection.execute(
        """
        SELECT u.id, u.username, u.display_name, u.role, u.must_change_password, s.last_seen_at,
               s.last_seen_at < datetime('now', '-1 minute') AS stale
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
          AND u.disabled = 0
          AND s.last_seen_at >= datetime('now', ?)
        """,
        (token_hash, f"-{int(idle_minutes)} minutes"),
    ).fetchone()
    if row is not None and row["stale"]:
        connection.execute(
            "UPDATE sessions SET last_seen_at = datetime('now') WHERE token_hash = ?",
            (token_hash,),
        )
    return row


def delete_session(connection: sqlite3.Connection, token_hash: str) -> None:
    connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def delete_sessions_for(
    connection: sqlite3.Connection, user_id: str, *, keep: str | None = None
) -> None:
    """Sign a person out everywhere, optionally except the session making the change."""
    connection.execute(
        "DELETE FROM sessions WHERE user_id = ? AND token_hash IS NOT ?",
        (user_id, keep),
    )


def prune_sessions(connection: sqlite3.Connection, idle_minutes: int) -> None:
    connection.execute(
        "DELETE FROM sessions WHERE last_seen_at < datetime('now', ?)",
        (f"-{int(idle_minutes)} minutes",),
    )
