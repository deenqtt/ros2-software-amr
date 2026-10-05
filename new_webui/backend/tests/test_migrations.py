"""
Migration runner.

The previous backend applied schema changes inside
``try/except Exception: pass``, which made "already applied" and "failed for a
real reason" indistinguishable. These tests pin the behaviour that replaces it.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.db import connect, discover_migrations, migrate


def test_migrations_are_numbered_and_unique():
    found = discover_migrations()
    assert found, "expected at least one migration"
    versions = [version for version, _, _ in found]
    assert versions == sorted(versions)
    assert len(versions) == len(set(versions))


def test_migrate_applies_and_records(settings):
    connection = connect(settings.db_path)
    applied = migrate(connection)
    assert applied == [version for version, _, _ in discover_migrations()]

    recorded = connection.execute("SELECT version FROM schema_migrations ORDER BY version")
    assert [row["version"] for row in recorded] == applied
    connection.close()


def test_migrate_is_idempotent(settings):
    connection = connect(settings.db_path)
    first = migrate(connection)
    second = migrate(connection)
    assert first != []
    assert second == [], "a second run must apply nothing"
    connection.close()


def test_failed_migration_rolls_back_and_raises(settings, tmp_path):
    """A broken migration must not leave half a schema behind."""
    broken = tmp_path / "migrations"
    broken.mkdir()
    (broken / "001_ok.sql").write_text("CREATE TABLE ok (id INTEGER PRIMARY KEY);")
    (broken / "002_broken.sql").write_text(
        "CREATE TABLE half (id INTEGER PRIMARY KEY); THIS IS NOT SQL;"
    )

    connection = connect(settings.db_path)
    with pytest.raises(sqlite3.Error):
        migrate(connection, broken)

    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert "ok" in tables, "the migration that succeeded should stand"
    assert "half" not in tables, "the failed migration must roll back entirely"

    recorded = connection.execute("SELECT version FROM schema_migrations").fetchall()
    assert [row["version"] for row in recorded] == [1]
    connection.close()


def test_rejects_unnumbered_migration_filename(tmp_path):
    bad = tmp_path / "migrations"
    bad.mkdir()
    (bad / "add_stuff.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="must start with a number"):
        discover_migrations(bad)


def test_foreign_keys_are_enforced(settings):
    """
    Cascades must be a deliberate schema decision.

    The old database enabled foreign keys but paired them with a read endpoint
    that deleted rows, so an ordinary GET could destroy an operator's zones,
    docks and destinations.
    """
    connection = connect(settings.db_path)
    row = connection.execute("PRAGMA foreign_keys").fetchone()
    assert row[0] == 1
    connection.close()


def test_super_admin_migration_keeps_sessions_and_audit_and_promotes_admins(settings, tmp_path):
    """
    009 rebuilds users to widen a CHECK constraint. Done with foreign keys on,
    dropping the old table would cascade: every session deleted, every audit
    record orphaned. Pin that the rebuild keeps both, and that existing admins
    become super admins so nobody loses the Users screen by upgrading.
    """
    import shutil

    from app.db import MIGRATIONS_DIR

    before = tmp_path / "before"
    before.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if int(path.stem.split("_")[0]) < 9:
            shutil.copy(path, before / path.name)

    connection = connect(settings.db_path)
    migrate(connection, before)
    connection.execute(
        "INSERT INTO users (id, username, role, password_hash) VALUES "
        "('u1', 'boss', 'admin', 'x'), ('u2', 'ops', 'operator', 'x')"
    )
    connection.execute("INSERT INTO sessions (token_hash, user_id) VALUES ('t1', 'u1')")
    connection.execute(
        "INSERT INTO audit_log (user_id, username, action) VALUES ('u1', 'boss', 'login')"
    )

    assert migrate(connection) == [
        version for version, _, _ in discover_migrations() if version >= 9
    ]

    roles = dict(connection.execute("SELECT username, role FROM users").fetchall())
    assert roles == {"boss": "super_admin", "ops": "operator"}
    assert connection.execute("SELECT user_id FROM sessions").fetchone()["user_id"] == "u1"
    assert connection.execute("SELECT user_id FROM audit_log").fetchone()["user_id"] == "u1"
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    # The rebuilt table still cascades: deleting a person ends their sessions.
    connection.execute("DELETE FROM users WHERE id = 'u1'")
    assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    connection.close()
