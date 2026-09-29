"""
Application factory.

Exports ``create_app`` and nothing else. Importing this module must not build
an app or read ``.env``: tests import it to construct an app against a
temporary database, and a module-level instance would read the developer's
real configuration on the way past. The ASGI entry point lives in asgi.py.
"""

from __future__ import annotations

import math
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import health, maps, missions, robots, stations, zones
from app.config import Settings, get_settings
from app.db import connect, migrate


def _json_safe(value: Any) -> Any:
    """
    Make a rejected value safe to echo back.

    FastAPI includes the offending input in a validation error, and JSON cannot
    represent NaN or infinity — so a request carrying one produced a 500 from the
    response encoder *after* validation had correctly rejected it. A malformed
    request must never read as a server fault.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


async def _on_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    detail = [
        # ctx carries the original exception object, which is not serialisable
        # either and adds nothing the message does not already say.
        {key: _json_safe(value) for key, value in entry.items() if key != "ctx"}
        for entry in error.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detail}
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    resolved.validate_for_runtime()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Migrations run once at startup, on a connection that is then closed.
        # Requests get their own connections; see api/deps.py.
        resolved.maps_dir.mkdir(parents=True, exist_ok=True)
        connection = connect(resolved.db_path)
        try:
            applied = migrate(connection)
            app.state.schema_versions_applied = applied
        finally:
            connection.close()
        yield

    app = FastAPI(
        title="AMR Backend",
        version="0.1.0",
        summary="Fleet registry and persistence for the AMR control interface.",
        lifespan=lifespan,
    )
    app.state.settings = resolved

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_credentials=True,
        # Only the methods this API serves. The old backend allowed every
        # method from every origin with no authentication at all.
        #
        # PUT is here because map assignment uses it. Its absence made the
        # Assign button fail the browser's preflight while curl and the tests —
        # neither of which preflights — worked, so nothing caught it.
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    app.add_exception_handler(RequestValidationError, _on_validation_error)

    app.include_router(health.router)
    app.include_router(robots.router)
    app.include_router(maps.router)
    app.include_router(stations.router)
    app.include_router(missions.router)
    app.include_router(missions.runs_router)
    app.include_router(zones.router)
    return app


if __name__ == "__main__":  # pragma: no cover
    # Running this file directly used to exit 0 having done nothing, which
    # looks exactly like success. Say what to run instead.
    raise SystemExit(
        "app/main.py is a factory module, not an entry point.\n"
        "Run the server with:  python -m app  (add --reload while developing)"
    )
