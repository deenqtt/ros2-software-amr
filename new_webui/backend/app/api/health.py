"""Liveness and readiness."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import Connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness only: the process is up. Says nothing about the database."""
    return {"status": "ok"}


@router.get("/ready")
def ready(
    request: Request,
    connection: Connection,
) -> JSONResponse:
    """
    Readiness: the database answers and the schema is current.

    Kept separate from /health so a container orchestrator can tell "starting"
    apart from "broken" — and so a monitoring check cannot report a healthy
    service that is actually unable to read its own tables.
    """
    try:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
        ).fetchone()
    except sqlite3.Error as error:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "detail": str(error)},
        )

    return JSONResponse(
        content={
            "status": "ready",
            "schema_version": int(row["version"]),
            "env": request.app.state.settings.env,
        }
    )
