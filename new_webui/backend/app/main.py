"""
Application factory.

Exports ``create_app`` and nothing else. Importing this module must not build
an app or read ``.env``: tests import it to construct an app against a
temporary database, and a module-level instance would read the developer's
real configuration on the way past. The ASGI entry point lives in asgi.py.
"""

from __future__ import annotations

import logging
import math
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import audit
from app.api import auth, health, maps, missions, robots, ros_proxy, stations, users, zones
from app.config import Settings, get_settings
from app.db import connect, migrate
from app.repositories import audit as audit_repo
from app.repositories import users as users_repo

log = logging.getLogger(__name__)


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


def bootstrap_account(connection, settings: Settings) -> None:
    """
    Create the first super admin from the environment, on an empty database.

    Only ever on an empty one: once anyone exists, the variables are ignored, so
    a password left in .env cannot recreate or reset an account later. The
    account must replace the password at first sign-in.
    """
    if not settings.bootstrap_user or settings.bootstrap_password is None:
        return
    if users_repo.count_users(connection) > 0:
        return

    from app.schemas.user import USERNAME_PATTERN
    from app.security import PASSWORD_MIN, hash_password

    username = settings.bootstrap_user.strip()
    password = settings.bootstrap_password.get_secret_value()
    if not USERNAME_PATTERN.match(username) or len(password) < PASSWORD_MIN:
        log.error(
            "AMR_BOOTSTRAP_USER / AMR_BOOTSTRAP_PASSWORD ignored: the username needs 3 to 32 "
            "letters, digits, dots, dashes or underscores, and the password %d characters.",
            PASSWORD_MIN,
        )
        return

    users_repo.create_user(
        connection,
        {
            "username": username,
            "role": "super_admin",
            "password_hash": hash_password(password),
            "must_change_password": 1,
        },
    )
    log.warning(
        "Created super admin '%s' from AMR_BOOTSTRAP_USER. It must set a new password at "
        "first sign-in; remove AMR_BOOTSTRAP_PASSWORD from the environment afterwards.",
        username,
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
            audit_repo.prune(connection, resolved.audit_retention_days)
            users_repo.prune_sessions(connection, resolved.session_idle_minutes)
            bootstrap_account(connection, resolved)
            if users_repo.count_active_super_admins(connection) == 0:
                log.warning(
                    "No super admin account exists, so nobody can manage accounts. Set "
                    "AMR_BOOTSTRAP_USER and AMR_BOOTSTRAP_PASSWORD, or run on this machine:  "
                    "python -m app create-admin <username>"
                )
        finally:
            connection.close()
        if resolved.is_production and resolved.agent_auth == "optional":
            log.warning(
                "AMR_AGENT_AUTH=optional: robot agents are let in without credentials, "
                "and so is anything else that calls the agent's endpoints."
            )
        if resolved.is_production and not resolved.cookie_secure:
            # Only reachable with AMR_ALLOW_INSECURE_HTTP=true; validate_for_runtime
            # refuses it otherwise. Said at every start so it is not forgotten.
            log.warning(
                "AMR_ALLOW_INSECURE_HTTP=true: serving production over plain HTTP. Session "
                "cookies and passwords cross the network unencrypted; enable TLS and set "
                "AMR_COOKIE_SECURE=true."
            )
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
    audit.install(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(users.audit_router)
    app.include_router(robots.router)
    app.include_router(ros_proxy.router)
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
