"""
Accounts, managed by super admins.

There is no self sign-up and no default password. The first super admin comes
from AMR_BOOTSTRAP_USER / AMR_BOOTSTRAP_PASSWORD on a fresh database, or from
``python -m app create-admin`` on the server, and has to replace that password
at first sign-in. Shipping admin/admin (MiR Fleet's documented defaults) is how
a fleet ends up drivable by anyone who has read the manual.

Every password set here is someone else's choice — a new account, a reset — so
it is marked must-change: the person replaces it the first time they sign in,
and the super admin who typed it no longer knows their password.
"""

from __future__ import annotations

import csv
import io
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import Connection
from app.auth import CurrentSuperAdmin, SuperAdmin
from app.db import transaction
from app.repositories import audit as audit_repo
from app.repositories import users as repo
from app.schemas.user import AuditEntryOut, AuditPageOut, UserCreate, UserOut, UserPatch
from app.security import hash_password, password_problem

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[SuperAdmin])
audit_router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[SuperAdmin])


def _to_out(row: sqlite3.Row) -> UserOut:
    return UserOut.model_validate(dict(row))


def _last_admin(error: repo.LastAdminError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, {"message": str(error)})


def _check_password(password: str, username: str) -> None:
    """
    The part of the password policy that needs the username.

    The rest (length, common passwords) is already enforced by the request
    schema; this repeats it harmlessly and adds "not the username".
    """
    problem = password_problem(password, username)
    if problem:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "password", "message": problem}
        )


@router.get("", response_model=list[UserOut])
def list_users(connection: Connection) -> list[UserOut]:
    return [_to_out(row) for row in repo.list_users(connection)]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, connection: Connection) -> UserOut:
    _check_password(body.password, body.username)
    try:
        with transaction(connection):
            row = repo.create_user(
                connection,
                {
                    "username": body.username,
                    "display_name": body.display_name,
                    "role": body.role,
                    "password_hash": hash_password(body.password),
                    "must_change_password": 1,
                },
            )
    except repo.DuplicateUserError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"field": "username", "message": str(error)}
        ) from error
    return _to_out(row)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str, body: UserPatch, admin: CurrentSuperAdmin, connection: Connection
) -> UserOut:
    """
    Rename, change role, disable, or reset a password.

    Disabling an account or resetting its password signs it out everywhere: a
    reset is usually because the old password got out, and a disabled account
    with a live session would not really be disabled.
    """
    target = repo.get_user(connection, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    patch = body.model_dump(exclude_unset=True)
    if patch.get("password") is not None:
        _check_password(patch["password"], target["username"])
    if user_id == admin.user_id and patch.get("disabled"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"message": "You cannot disable your own account"}
        )

    password = patch.pop("password", None)
    if password is not None:
        patch["password_hash"] = hash_password(password)
        # A reset is a temporary password, unless you are resetting your own.
        patch["must_change_password"] = 0 if user_id == admin.user_id else 1
    if "disabled" in patch:
        patch["disabled"] = int(bool(patch["disabled"]))

    try:
        with transaction(connection):
            row = repo.update_user(connection, user_id, patch)
            if password is not None or patch.get("disabled"):
                # The admin resetting their own password keeps their own session.
                keep = admin.session if user_id == admin.user_id else None
                repo.delete_sessions_for(connection, user_id, keep=keep)
    except repo.LastAdminError as error:
        raise _last_admin(error) from error

    if row is None:  # pragma: no cover — existence was just checked
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return _to_out(row)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, admin: CurrentSuperAdmin, connection: Connection) -> Response:
    """
    Remove an account. Their audit records stay, with the name they had.

    Disabling is usually the better choice; this exists for accounts made by
    mistake.
    """
    if user_id == admin.user_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"message": "You cannot delete your own account"}
        )
    try:
        with transaction(connection):
            deleted = repo.delete_user(connection, user_id)
    except repo.LastAdminError as error:
        raise _last_admin(error) from error
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


AuditKind = Literal["all", "changes", "sign-ins", "refused"]
EXPORT_MAX_ROWS = 50_000


def _utc_stamp(value: datetime | None) -> str | None:
    """The server's own stamp format, so a range compares as text in SQL."""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _audit_filter(
    kind: Annotated[AuditKind, Query()] = "all",
    user_id: Annotated[str | None, Query()] = None,
    since: Annotated[datetime | None, Query(description="From this moment (ISO 8601).")] = None,
    until: Annotated[datetime | None, Query(description="Before this moment (ISO 8601).")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Text in any field.")] = None,
    upto_id: Annotated[int | None, Query(ge=0, description="Pin the reading.")] = None,
) -> audit_repo.AuditFilter:
    return audit_repo.AuditFilter(
        kind=kind,
        user_id=user_id or None,
        since=_utc_stamp(since),
        until=_utc_stamp(until),
        search=(q or "").strip() or None,
        upto_id=upto_id,
    )


AuditQuery = Annotated[audit_repo.AuditFilter, Depends(_audit_filter)]


@audit_router.get("", response_model=AuditPageOut)
def list_audit(
    connection: Connection,
    audit_filter: AuditQuery,
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditPageOut:
    """
    One page of the trail, newest first, with the total for the filter.

    The first request leaves ``upto_id`` out and gets back the newest id; later
    pages send it, so a busy floor writing records while someone pages through
    does not slide rows from one page onto the next.
    """
    if audit_filter.upto_id is None:
        audit_filter = replace(audit_filter, upto_id=audit_repo.newest_id(connection))
    rows = audit_repo.list_page(connection, audit_filter, limit=limit, offset=offset)
    return AuditPageOut(
        items=[AuditEntryOut.model_validate(dict(row)) for row in rows],
        total=audit_repo.count(connection, audit_filter),
        upto_id=audit_filter.upto_id or 0,
    )


_CSV_COLUMNS = (
    "id", "at", "username", "role", "action", "method", "path", "status", "detail", "ip",
)


@audit_router.get("/export.csv")
def export_audit(connection: Connection, audit_filter: AuditQuery) -> Response:
    """
    The filtered trail as CSV, for whoever asks "who changed what" after the fact.

    Capped, so an unfiltered export of a long retention window cannot tie the
    server up; the header says when the cap cut it short. Times are UTC, as
    stored, and say so in the column name.
    """
    rows = audit_repo.list_page(connection, audit_filter, limit=EXPORT_MAX_ROWS + 1)
    truncated = len(rows) > EXPORT_MAX_ROWS
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "at_utc", *_CSV_COLUMNS[2:]])
    for row in rows[:EXPORT_MAX_ROWS]:
        writer.writerow([_csv_safe(row[column]) for column in _CSV_COLUMNS])
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    headers = {"Content-Disposition": f'attachment; filename="activity-{stamp}.csv"'}
    if truncated:
        headers["X-Truncated"] = str(EXPORT_MAX_ROWS)
    return Response(buffer.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)


def _csv_safe(value: object) -> object:
    """
    Defuse spreadsheet formulas.

    A username or path is typed by whoever sent the request — including a failed
    sign-in from anyone on the network. A cell starting with = + - @ runs as a
    formula when the CSV is opened in a spreadsheet, so it is prefixed with a
    quote, the OWASP-recommended neutraliser. Leading whitespace does not hide
    it: spreadsheets skip spaces before the sign, so the first non-blank
    character is what counts (a leading tab or CR is neutralised outright).
    Negative numbers stored as numbers are not strings and stay untouched; a
    string like "-5" is prefixed too, since it cannot be told from "-1+1".
    """
    if isinstance(value, str) and (
        value[:1] in ("\t", "\r") or value.lstrip()[:1] in ("=", "+", "-", "@")
    ):
        return "'" + value
    return value
