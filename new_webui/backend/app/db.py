"""
SQLite access and schema migrations.

Two things the previous backend got wrong are fixed here by construction.

1. **Migrations are numbered, ordered and recorded.** The old code ran a list
   of ``ALTER TABLE`` statements inside ``try/except Exception: pass``, so a
   migration that failed for a real reason was indistinguishable from one that
   had already been applied.

2. **Reads never mutate.** ``GET /api/maps`` used to scan the filesystem and
   delete rows whose file was missing — which, through ``ON DELETE CASCADE``,
   silently destroyed every keepout zone, dock and destination attached to that
   map. Scanning is a separate, explicit operation here.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(db_path: Path) -> sqlite3.Connection:
    """
    Open a connection with the pragmas this application depends on.

    ``check_same_thread=False`` is required, not a shortcut. FastAPI runs a
    sync dependency in its threadpool but an ``async def`` endpoint on the
    event loop, so a connection handed to an async endpoint is created in one
    thread and used in another — and sqlite refuses that by default. The
    multipart upload endpoint has to be async to await the file bodies.

    It is safe here because a connection is created per request, used by one
    request, and closed with it. Nothing shares a connection between requests,
    and nothing spawns concurrent tasks against one.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    # WAL so a read cannot block the writer; foreign keys so a cascade is a
    # deliberate schema decision rather than an accident of enforcement.
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _applied_versions(connection: sqlite3.Connection) -> set[int]:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     INTEGER PRIMARY KEY,
            name        TEXT    NOT NULL,
            applied_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[tuple[int, str, Path]]:
    """Return ``(version, name, path)`` for every migration, in order."""
    found: list[tuple[int, str, Path]] = []
    for path in sorted(directory.glob("*.sql")):
        version_text, _, name = path.stem.partition("_")
        if not version_text.isdigit():
            raise ValueError(f"Migration filename must start with a number: {path.name}")
        found.append((int(version_text), name or path.stem, path))

    versions = [version for version, _, _ in found]
    duplicates = {v for v in versions if versions.count(v) > 1}
    if duplicates:
        raise ValueError(f"Duplicate migration versions: {sorted(duplicates)}")
    return found


def migrate(connection: sqlite3.Connection, directory: Path = MIGRATIONS_DIR) -> list[int]:
    """
    Apply every migration that has not run yet. Returns the versions applied.

    Each migration runs in its own transaction: a failure rolls that migration
    back and stops, rather than leaving the schema half-updated.
    """
    applied = _applied_versions(connection)
    newly_applied: list[int] = []

    for version, name, path in discover_migrations(directory):
        if version in applied:
            continue

        # executescript() issues an implicit COMMIT before it runs, so wrapping
        # the call in BEGIN/COMMIT from Python does not work — the BEGIN is
        # committed away and the later COMMIT fails with "no transaction is
        # active". The transaction has to live inside the script itself.
        #
        # The bookkeeping INSERT goes in the same script, so a migration and
        # the record of it are applied or discarded together. Neither value is
        # user input: the version is digits parsed from the filename and the
        # name is the rest of that filename, quoted.
        statements = path.read_text(encoding="utf-8").rstrip().rstrip(";")
        escaped_name = name.replace("'", "''")
        script = (
            "BEGIN;\n"
            f"{statements};\n"
            "INSERT INTO schema_migrations (version, name) "
            f"VALUES ({int(version)}, '{escaped_name}');\n"
            "COMMIT;"
        )

        try:
            connection.executescript(script)
        except Exception:
            # A failed script leaves its transaction open; close it so the
            # connection is still usable and the partial schema is discarded.
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        newly_applied.append(version)

    return newly_applied


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block atomically. Rolls back on any exception."""
    connection.execute("BEGIN")
    try:
        yield connection
    except Exception:
        connection.execute("ROLLBACK")
        raise
    connection.execute("COMMIT")
