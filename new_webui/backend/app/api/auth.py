"""
Sign in, sign out, and the caller's own account.

The session is an HttpOnly cookie, not a token the page stores. Script on the
page cannot read it, so a cross-site-scripting bug cannot walk off with a
session; SameSite=Lax keeps another site from riding it with a forged POST.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request, Response, status

from app import audit
from app.api.deps import Connection
from app.auth import SESSION_COOKIE, CurrentUser, Principal, signed_in
from app.db import transaction
from app.repositories import users as repo
from app.schemas.user import LoginIn, MeOut, PasswordChangeIn
from app.security import DUMMY_HASH, hash_password, hash_token, new_session_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Failed sign-ins allowed per name and address before a pause. Low enough to make
# guessing impractical, high enough that someone fumbling a password on a
# touchscreen in gloves is not locked out of their shift.
FAILURES_ALLOWED = 5
FAILURE_WINDOW_S = 300.0


class LoginThrottle:
    """
    Counts recent failures per (address, name), in memory.

    In memory is enough for one backend process, which is what this is. A
    restart forgets the counts, and an attacker who can restart the server has
    better options than guessing.
    """

    def __init__(self) -> None:
        self._failures: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: tuple[str, str], now: float) -> deque[float]:
        times = self._failures.setdefault(key, deque())
        while times and now - times[0] > FAILURE_WINDOW_S:
            times.popleft()
        return times

    def retry_after(self, key: tuple[str, str]) -> int:
        """Seconds until another attempt is allowed, or 0."""
        now = time.monotonic()
        with self._lock:
            times = self._recent(key, now)
            if len(times) < FAILURES_ALLOWED:
                return 0
            return max(1, int(FAILURE_WINDOW_S - (now - times[0])) + 1)

    def fail(self, key: tuple[str, str]) -> None:
        now = time.monotonic()
        with self._lock:
            self._recent(key, now).append(now)

    def clear(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._failures.pop(key, None)


def _throttle(request: Request) -> LoginThrottle:
    state = request.app.state
    if not hasattr(state, "login_throttle"):
        state.login_throttle = LoginThrottle()
    return state.login_throttle


def _me(principal: Principal, request: Request) -> MeOut:
    return MeOut(
        id=principal.user_id,
        username=principal.username,
        display_name=principal.display_name,
        role=principal.role,
        session_idle_minutes=request.app.state.settings.session_idle_minutes,
        must_change_password=principal.must_change_password,
    )


@router.post("/login", response_model=MeOut)
def login(body: LoginIn, request: Request, response: Response, connection: Connection) -> MeOut:
    """
    Check a name and password and start a session.

    Every refusal says the same thing. "No such user" and "wrong password" are
    different facts, and telling them apart tells a guesser which names to try.
    """
    settings = request.app.state.settings
    key = (audit.client_ip(request) or "", body.username.strip().lower())
    throttle = _throttle(request)

    wait = throttle.retry_after(key)
    if wait:
        audit.record(
            connection,
            request,
            principal=None,
            username=body.username,
            action="login",
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="throttled",
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many failed sign-ins. Try again in {max(1, round(wait / 60))} minute(s).",
            headers={"Retry-After": str(wait)},
        )

    row = repo.get_credentials(connection, body.username.strip())
    # Verify even when there is no such user, so both refusals take as long.
    password_ok = verify_password(body.password, row["password_hash"] if row else DUMMY_HASH)

    if row is None or not password_ok or row["disabled"]:
        throttle.fail(key)
        reason = (
            "unknown user" if row is None else "disabled" if row["disabled"] else "bad password"
        )
        audit.record(
            connection,
            request,
            principal=None,
            username=body.username,
            action="login",
            status=status.HTTP_401_UNAUTHORIZED,
            detail=reason,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")

    throttle.clear(key)
    token = new_session_token()
    with transaction(connection):
        repo.prune_sessions(connection, settings.session_idle_minutes)
        repo.create_session(
            connection, hash_token(token), row["id"], request.headers.get("user-agent")
        )
        repo.mark_login(connection, row["id"])

    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
        # No max-age: the cookie lasts as long as the browser session, and the
        # server's idle limit decides when the session itself ends.
    )

    principal = Principal(
        kind="user",
        user_id=row["id"],
        username=row["username"],
        display_name=row["display_name"],
        role=row["role"],
        must_change_password=bool(row["must_change_password"]),
    )
    audit.record(
        connection, request, principal=principal, action="login", status=status.HTTP_200_OK
    )
    return _me(principal, request)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, connection: Connection) -> Response:
    """End this browser's session. Succeeds when already signed out: the goal is met."""
    principal = signed_in(request, connection)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        repo.delete_session(connection, hash_token(token))
    if principal is not None:
        audit.record(
            connection,
            request,
            principal=principal,
            action="logout",
            status=status.HTTP_204_NO_CONTENT,
        )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me", response_model=MeOut)
def me(principal: CurrentUser, request: Request) -> MeOut:
    """Who is signed in. 401 when nobody is, which is how the UI knows to show sign-in."""
    return _me(principal, request)


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: PasswordChangeIn, principal: CurrentUser, connection: Connection
) -> Response:
    """
    Change your own password.

    Asks for the current one, so a screen left signed in cannot be used to lock
    its owner out. Signs out every other browser, which is usually why someone
    changes a password.
    """
    stored = repo.get_password_hash(connection, principal.user_id)
    if stored is None or not verify_password(body.current_password, stored):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"field": "current_password", "message": "Current password is wrong"},
        )
    if body.new_password == body.current_password:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "field": "new_password",
                "message": "Choose a password different from the current one",
            },
        )
    with transaction(connection):
        repo.update_user(
            connection,
            principal.user_id,
            {"password_hash": hash_password(body.new_password), "must_change_password": 0},
        )
        repo.delete_sessions_for(connection, principal.user_id, keep=principal.session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
