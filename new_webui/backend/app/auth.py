"""
Who is calling, and whether they may.

Every route declares the least role it needs, through one of the dependencies at
the bottom of this module. Nothing checks a role inline in a handler: a check
that lives in one place is a check that can be read in one place.

A request is either a signed-in person (session cookie) or a robot agent. An
agent presents ``Authorization: Bearer <token>``, a token an admin minted for one
robot; it is accepted only on the endpoints an agent uses, and binds the caller
to that robot. A bearer token that does not match is refused outright — it never
falls through to being treated as anonymous.

The old way in, "not signed in at all means agent", survives only for local
development: ``AMR_AGENT_AUTH=optional`` outside production, with no cookie and
no Authorization header on the request. Production refuses to start with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import Connection
from app.repositories import robots as robots_repo
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
    #: The one robot an agent may act for. None for people, and for the
    #: unbound development-only agent (``AMR_AGENT_AUTH=optional``).
    robot_id: str | None = None

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
        settings = request.app.state.settings
        # Both limits, here and only here: the WebSocket relay and every route
        # find the signed-in person through this function.
        row = users_repo.resolve_session(
            connection, token_hash, settings.session_idle_minutes, settings.session_max_hours
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


#: The unbound agent of ``AMR_AGENT_AUTH=optional`` (development only).
AGENT = Principal(kind="agent", username="agent")


PASSWORD_CHANGE_REQUIRED = "password_change_required"  # noqa: S105 — an error code, not a secret


def _unauthorized(message: str = "Sign in to continue", scheme: str = "Cookie") -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, message, headers={"WWW-Authenticate": scheme}
    )


def _bearer_token(request: Request) -> str | None:
    """The token of an ``Authorization: Bearer`` header, "" if malformed, None if absent."""
    header = request.headers.get("authorization")
    if header is None:
        return None
    scheme, _, token = header.strip().partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip()


def agent_from_token(connection: Connection, token: str) -> Principal | None:
    """The agent this token belongs to, bound to its robot, or None."""
    if not token:
        return None
    row = robots_repo.get_robot_by_agent_token(connection, hash_token(token))
    if row is None:
        return None
    return Principal(
        kind="agent",
        username=f"agent:{row['name'] or row['id']}",
        robot_id=row["id"],
    )


def _agent(request: Request, connection: Connection) -> Principal | None:
    """
    The robot agent behind this request, if it is one; raises on a bad token.

    Not cached on ``request.state.principal``: a stricter guard on the same
    request must still see "nobody signed in" and answer 401.
    """
    token = _bearer_token(request)
    if token is not None:
        bound = agent_from_token(connection, token)
        if bound is None:
            # A wrong token is a refusal, never a reason to try something else.
            raise _unauthorized("Invalid agent token", "Bearer")
        return bound

    if signed_in(request, connection) is not None:
        return None
    settings = request.app.state.settings
    if (
        settings.agent_auth == "optional"
        and not settings.is_production
        and SESSION_COOKIE not in request.cookies
        and "authorization" not in request.headers
    ):
        # Development only, and only for a request that carries no credential
        # at all: a stale or forged cookie is a person who must sign in again,
        # not a robot.
        return AGENT
    return None


def _require(minimum: Role, *, agent: bool, pending_ok: bool = False):
    def dependency(request: Request, connection: Connection) -> Principal:
        if agent:
            # A bearer token is looked at first, and only on agent endpoints:
            # it never stands in for a person on any other guard.
            robot_agent = _agent(request, connection)
            if robot_agent is not None:
                # Recorded as the actor for the audit trail, but never cached
                # as the signed-in principal.
                request.state.actor = robot_agent
                return robot_agent

        principal = signed_in(request, connection)
        if principal is None:
            raise _unauthorized()
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


def ensure_robot(principal: Principal, robot_id: str) -> None:
    """
    Refuse an agent acting on a robot that is not its own.

    People are unaffected: their role already decided what they may do. An
    unbound agent (development only) is not limited either.
    """
    if principal.kind == "agent" and principal.robot_id is not None:
        if principal.robot_id != robot_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "This agent token belongs to another robot"
            )


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
