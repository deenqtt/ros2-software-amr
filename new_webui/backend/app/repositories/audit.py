"""Audit trail: append and read. Nothing here updates or deletes a single record."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Literal

_COLUMNS = "id, at, user_id, username, role, action, method, path, status, detail, ip"


def record(connection: sqlite3.Connection, entry: dict) -> None:
    connection.execute(
        """
        INSERT INTO audit_log (user_id, username, role, action, method, path, status, detail, ip)
        VALUES (:user_id, :username, :role, :action, :method, :path, :status, :detail, :ip)
        """,
        {
            "user_id": None,
            "username": None,
            "role": None,
            "method": None,
            "path": None,
            "status": None,
            "detail": None,
            "ip": None,
            **entry,
        },
    )


@dataclass(frozen=True)
class AuditFilter:
    """
    Which records to read. Every field optional; empty means everything.

    ``upto_id`` pins a reading: the client takes the newest id when it opens
    the log and sends it with every page, so records written while someone is
    paging do not shift page 3 onto what page 2 already showed.
    """

    kind: Literal["all", "changes", "sign-ins", "refused"] = "all"
    user_id: str | None = None
    since: str | None = None
    until: str | None = None
    search: str | None = None
    upto_id: int | None = None


_SIGN_IN_ACTIONS = "('login', 'logout')"


def _where(audit_filter: AuditFilter) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []
    if audit_filter.kind == "changes":
        clauses.append(f"action NOT IN {_SIGN_IN_ACTIONS}")
    elif audit_filter.kind == "sign-ins":
        clauses.append(f"action IN {_SIGN_IN_ACTIONS}")
    elif audit_filter.kind == "refused":
        clauses.append("status >= 400")
    if audit_filter.user_id is not None:
        clauses.append("user_id = ?")
        params.append(audit_filter.user_id)
    if audit_filter.since is not None:
        clauses.append("at >= ?")
        params.append(audit_filter.since)
    if audit_filter.until is not None:
        clauses.append("at < ?")
        params.append(audit_filter.until)
    if audit_filter.upto_id is not None:
        clauses.append("id <= ?")
        params.append(audit_filter.upto_id)
    if audit_filter.search:
        # A plain substring, case-insensitive; % and _ typed by a person mean
        # themselves, not wildcards.
        needle = "%" + re.sub(r"([\\%_])", r"\\\1", audit_filter.search.strip()) + "%"
        clauses.append(
            "(username LIKE ? ESCAPE '\\' OR action LIKE ? ESCAPE '\\' OR path LIKE ? ESCAPE '\\' "
            "OR detail LIKE ? ESCAPE '\\' OR ip LIKE ? ESCAPE '\\')"
        )
        params.extend([needle] * 5)
    return (f"WHERE {' AND '.join(clauses)}" if clauses else ""), params


def list_page(
    connection: sqlite3.Connection, audit_filter: AuditFilter, *, limit: int, offset: int = 0
) -> list[sqlite3.Row]:
    """Newest first."""
    where, params = _where(audit_filter)
    return connection.execute(
        f"SELECT {_COLUMNS} FROM audit_log {where} ORDER BY id DESC LIMIT ? OFFSET ?",  # noqa: S608 — fixed clauses
        (*params, limit, offset),
    ).fetchall()


def count(connection: sqlite3.Connection, audit_filter: AuditFilter) -> int:
    where, params = _where(audit_filter)
    row = connection.execute(
        f"SELECT count(*) AS n FROM audit_log {where}",  # noqa: S608 — fixed clauses
        params,
    ).fetchone()
    return int(row["n"])


def newest_id(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT max(id) AS n FROM audit_log").fetchone()
    return int(row["n"] or 0)


def prune(connection: sqlite3.Connection, retention_days: int) -> int:
    """Drop records older than the retention window. Returns how many went."""
    return connection.execute(
        "DELETE FROM audit_log WHERE at < datetime('now', ?)",
        (f"-{int(retention_days)} days",),
    ).rowcount
