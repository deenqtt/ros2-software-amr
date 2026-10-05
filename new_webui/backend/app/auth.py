"""
Who is calling, and whether they may.

Every route declares the least role it needs, through one of the dependencies at
the bottom of this module. Nothing checks a role inline in a handler: a check
that lives in one place is a check that can be read in one place.

A request is either a signed-in person (session cookie) or a robot agent. Until
agents carry their own credentials, an agent is recognised only by *not* being
signed in, and only on the endpoints an agent uses, and only while
``AMR_AGENT_AUTH=optional``. That window is deliberate and named, so it can be
shut with one setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import Connection
from app.repositories import users as users_repo
from app.security import hash_token

Role = Literal["viewer", "operator", "admin", "super_admin"]
ROLES: tuple[Role, ...] = ("viewer", "operator", "admin", "super_admin")
_RANK = {role: rank for rank, role in enumerate(ROLES)}

SESSION_COOKIE = "amr_session"


@dataclass(frozen=True)
class Principal:
    kind: Literal["user", "agent"]
    user_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    role: Role | None = None
    #: The session's token hash, so a password change can keep this session.
    session: str | None = None
    #: Signed in with a password someone else chose; may only replace it.
    must_change_password: bool = False

    def at_least(self, role: Role) -> bool:
        return self.role is not None and _RANK[self.role] >= _RANK[role]


def signed_in(request: Request, connection: Connection) -> Principal | None:
    """
    The person behind this request's session cookie, or None.

    Resolved once per request and kept on ``request.state``: a route guarded by
    its router and again by itself would otherwise look the session up twice,
    and the audit middleware reads it from there afterwards.
    """
    if hasattr(request.state, "principal"):
        return request.state.principal

    principal: Principal | None = None
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        token_hash = hash_token(token)
        row = users_repo.resolve_session(
            connection, token_hash, request.app.state.settings.session_idle_minutes
        )
        if row is not None:
            principal = Principal(
                kind="user",
                user_id=row["id"],
                username=row["username"],
                display_name=row["display_name"],
                role=row["role"],
                session=token_hash,
                must_change_password=bool(row["must_change_password"]),
            )
    request.state.principal = principal
    return principal


AGENT = Principal(kind="agent", username="agent")


PASSWORD_CHANGE_REQUIRED = "password_change_required"  # noqa: S105 — an error code, not a secret


def _require(minimum: Role, *, agent: bool, pending_ok: bool = False):
    def dependency(request: Request, connection: Connection) -> Principal:
        principal = signed_in(request, connection)
        if principal is None:
            if agent and request.app.state.settings.agent_auth == "optional":
                # Recorded as the actor for the audit trail, but never cached as
                # the signed-in principal: a stricter guard on the same request
                # must still see "nobody signed in" and answer 401.
                request.state.actor = AGENT
                return AGENT
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Sign in to continue",
                headers={"WWW-Authenticate": "Cookie"},
            )
        if principal.must_change_password and not pending_ok:
            # Everything but reading who you are, changing the password and
            # signing out waits until a password someone else chose is replaced.
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                {
                    "message": "Set a new password before doing anything else.",
                    "code": PASSWORD_CHANGE_REQUIRED,
                },
            )
        if not principal.at_least(minimum):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                {
                    "message": (
                        f"This needs the {minimum} role; you are signed in as {principal.role}."
                    ),
                    "required_role": minimum,
                },
            )
        request.state.actor = principal
        return principal

    return dependency


# Read anything. People of any role, and the robot agent.
require_reader = _require("viewer", agent=True)
# Run and stop missions, switch a robot's mode.
require_operator = _require("operator", agent=False)
require_operator_or_agent = _require("operator", agent=True)
# Change the site: maps, stations, zones, missions, robots.
require_admin = _require("admin", agent=False)
require_admin_or_agent = _require("admin", agent=True)
# People and the audit trail.
require_super_admin = _require("super_admin", agent=False)
# Signed in at all, any role, even before replacing a temporary password. For
# the caller's own account only.
require_user = _require("viewer", agent=False, pending_ok=True)

Reader = Depends(require_reader)
Operator = Depends(require_operator)
OperatorOrAgent = Depends(require_operator_or_agent)
Admin = Depends(require_admin)
AdminOrAgent = Depends(require_admin_or_agent)
SuperAdmin = Depends(require_super_admin)

CurrentUser = Annotated[Principal, Depends(require_user)]
CurrentOperator = Annotated[Principal, Depends(require_operator)]
CurrentAdmin = Annotated[Principal, Depends(require_admin)]
CurrentSuperAdmin = Annotated[Principal, Depends(require_super_admin)]
