"""
The audit trail: every change made through the API, and every sign-in attempt.

Changes are recorded by one middleware rather than by each handler, so a new
endpoint is audited without anyone remembering to. Sign-ins are recorded by the
auth endpoints themselves, because a failed one has no principal for the
middleware to read.
"""

from __future__ import annotations

import logging
import sqlite3

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.auth import Principal
from app.db import connect
from app.repositories import audit as audit_repo

log = logging.getLogger(__name__)

_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Recorded by their own handlers (see api/auth.py), with more to say than a
# status code: which name was tried, and why it was refused.
_SELF_RECORDING = frozenset({"/api/auth/login", "/api/auth/logout"})


def client_ip(request: Request) -> str | None:
    # Behind nginx every request arrives from 127.0.0.1; the example config
    # forwards the real address. Only trusted when the backend listens on
    # loopback, i.e. nothing but nginx can have set it.
    forwarded = request.headers.get("x-real-ip")
    if forwarded and request.client and request.client.host in ("127.0.0.1", "::1"):
        return forwarded
    return request.client.host if request.client else None


def record(
    connection: sqlite3.Connection,
    request: Request,
    *,
    principal: Principal | None,
    action: str,
    status: int | None,
    username: str | None = None,
    detail: str | None = None,
) -> None:
    audit_repo.record(
        connection,
        {
            "user_id": principal.user_id if principal else None,
            "username": username or (principal.username if principal else None),
            "role": principal.role if principal else None,
            "action": action,
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "detail": detail,
            "ip": client_ip(request),
        },
    )


def _is_agent_progress(request: Request, principal: Principal | None) -> bool:
    # An agent reports progress on every step of every lap. Recording each one
    # would bury the changes people made under thousands of rows nobody reads;
    # the run itself already keeps that history.
    return (
        principal is not None
        and principal.kind == "agent"
        and request.method == "PATCH"
        and request.url.path.startswith("/api/runs/")
    )


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def audit_changes(request: Request, call_next) -> Response:
        response = await call_next(request)

        if request.method not in _MUTATING or request.url.path in _SELF_RECORDING:
            return response

        state = request.state
        principal: Principal | None = getattr(state, "actor", None) or getattr(
            state, "principal", None
        )
        # Nobody identified (refused before any guard ran, or an unknown path):
        # there is no one to attribute it to, and a 401 storm from a stale tab
        # is not an event worth keeping.
        if principal is None or _is_agent_progress(request, principal):
            return response

        try:
            connection = connect(app.state.settings.db_path)
            try:
                record(
                    connection,
                    request,
                    principal=principal,
                    action=f"{request.method} {request.url.path}",
                    status=response.status_code,
                )
            finally:
                connection.close()
        except sqlite3.Error:
            # The change itself has already happened and been answered; failing
            # the audit write must not turn a success into an error after the fact.
            log.exception("Could not write audit record for %s %s", request.method, request.url)
        return response
