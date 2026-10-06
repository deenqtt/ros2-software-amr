"""
The browser's only way to a robot's rosbridge: ``WS /api/robots/{id}/ros``.

rosbridge has no authentication. When browsers connected to it directly, every
role check lived in the browser, and anyone on the network could drive a robot
with a few lines of JavaScript. Now the robot's rosbridge port is reachable from
this server only, and this relay stands in front of it:

- who is calling comes from the session cookie, as for every other endpoint;
- every frame the browser sends is checked by ``ros_policy.decide`` and either
  forwarded unchanged or answered with a refusal — never both;
- what the robot sends back is forwarded as-is (maps and costmaps included,
  which is why the frame limit is raised well past websockets' 1 MiB default);
- commands that change what the robot does are written to the audit trail.

The session is looked up again before every audited command, before any other
frame once the last look-up is ten seconds old, and every ten seconds by a
watchdog even when the browser sends nothing — so signing someone out, disabling
them or lowering their role takes effect on an open socket within ten seconds,
including one that only receives telemetry. Between those look-ups teleop
frames, at 10 Hz, never touch the database.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sqlite3
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from app import auth
from app.audit import client_ip
from app.db import connect
from app.repositories import audit as audit_repo
from app.repositories import robots as robots_repo
from app.ros_policy import Decision, decide

log = logging.getLogger(__name__)

router = APIRouter(tags=["robots"])

#: Maps and costmaps are sent whole; a large warehouse map is several MB of JSON.
MAX_FRAME = 64 * 2**20
#: How stale the cached session may get before a frame is judged on it. Bounds
#: how long a signed-out or demoted person can keep driving by teleop.
RESOLVE_EVERY_S = 10.0
#: How often the watchdog checks the session of a socket that may be silent.
SESSION_CHECK_S = 10.0
#: The same refused command is recorded once per this many seconds per socket,
#: so a script hammering a forbidden service cannot fill the audit table.
DENIED_AUDIT_EVERY_S = 10.0

CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404
CLOSE_UPSTREAM_DOWN = 1011


class Upstream(Protocol):
    async def send(self, message: str) -> None: ...
    async def recv(self) -> str | bytes: ...
    async def close(self) -> None: ...


Connector = Callable[[str], Awaitable[Upstream]]


async def connect_rosbridge(url: str) -> Upstream:
    return await ws_connect(url, max_size=MAX_FRAME, open_timeout=5)


def _origin_ok(websocket: WebSocket) -> bool:
    """
    Cross-site WebSocket hijacking guard.

    Browsers send cookies on a WebSocket handshake to any site, and CORS does not
    apply to WebSockets. Without this, any page a signed-in operator visits
    could open this socket with their session and drive the robot.

    An Origin listed in cors_origins is accepted. Otherwise it must name this
    very host (Host header, port included) over http or https.

    The scheme is compared only when the backend knows it is serving TLS (scope
    scheme ``wss``): then the page must be https. That is the case when TLS ends
    at a proxy uvicorn trusts (FORWARDED_ALLOW_IPS: 127.0.0.1 for a host nginx,
    the web container's address in Docker) and it says so in X-Forwarded-Proto.
    When it sees ``ws`` it cannot tell plain HTTP from an untrusted proxy;
    requiring http there would refuse such sites, and accepting either gives
    nothing to anyone who cannot already serve pages on this exact host name.
    """
    origin = websocket.headers.get("origin")
    if not origin:
        return False
    if origin in websocket.app.state.settings.cors_origins:
        return True
    host = websocket.headers.get("host")
    if not host:
        return False
    parsed = urlparse(origin)
    if parsed.netloc != host or parsed.scheme not in ("http", "https"):
        return False
    return websocket.url.scheme != "wss" or parsed.scheme == "https"


def _target(frame: dict) -> str:
    name = frame.get("service") if frame.get("op") == "call_service" else frame.get("topic")
    return str(name)[:120] if name is not None else "-"


def _refusal(frame: Any, reason: str) -> str:
    frame_id = frame.get("id") if isinstance(frame, dict) else None
    if isinstance(frame, dict) and frame.get("op") == "call_service":
        return json.dumps(
            {
                "op": "service_response",
                "id": frame_id,
                "service": frame.get("service"),
                "result": False,
                "values": f"forbidden: {reason}",
            }
        )
    return json.dumps(
        {"op": "status", "level": "error", "msg": f"forbidden: {reason}", "id": frame_id}
    )


class _Session:
    """The caller, re-read from the database when it matters."""

    def __init__(self, websocket: WebSocket, connection: sqlite3.Connection) -> None:
        self.websocket = websocket
        self.connection = connection
        self.principal: auth.Principal | None = None
        self.resolved_at = 0.0

    def resolve(self) -> auth.Principal | None:
        # signed_in caches on the connection's state; a fresh answer is the point.
        with contextlib.suppress(AttributeError, KeyError):
            del self.websocket.state.principal
        self.principal = auth.signed_in(self.websocket, self.connection)  # type: ignore[arg-type]
        self.resolved_at = time.monotonic()
        return self.principal

    def stale(self) -> bool:
        return time.monotonic() - self.resolved_at >= RESOLVE_EVERY_S


@router.websocket("/api/robots/{robot_id}/ros")
async def ros_bridge(websocket: WebSocket, robot_id: str) -> None:
    if not _origin_ok(websocket):
        # Refused at the handshake: nothing about this server is worth telling
        # a page from another site.
        await websocket.close(code=CLOSE_FORBIDDEN)
        return

    settings = websocket.app.state.settings
    connection = connect(settings.db_path)
    try:
        # Accepted first and closed with a code, so the browser can tell
        # "sign in again" from "robot unreachable" (a refused handshake reads
        # as a bare 1006 to it).
        await websocket.accept()
        session = _Session(websocket, connection)
        principal = session.resolve()
        if principal is None:
            await websocket.close(code=CLOSE_UNAUTHENTICATED, reason="Sign in to continue")
            return
        if principal.must_change_password:
            await websocket.close(code=CLOSE_FORBIDDEN, reason=auth.PASSWORD_CHANGE_REQUIRED)
            return
        robot = robots_repo.get_robot(connection, robot_id)
        if robot is None:
            await websocket.close(code=CLOSE_NOT_FOUND, reason="No such robot")
            return

        connector: Connector = getattr(websocket.app.state, "ros_connect", connect_rosbridge)
        try:
            upstream = await connector(robot["bridge_url"])
        except Exception as error:  # any failure means "not reachable"
            log.info("rosbridge for robot %s unreachable: %s", robot_id, error)
            await websocket.close(code=CLOSE_UPSTREAM_DOWN, reason="Robot unreachable")
            return

        relay = _Relay(websocket, upstream, session, robot_id, robot["namespace"] or "")
        try:
            await relay.run()
        finally:
            with contextlib.suppress(Exception):
                await upstream.close()
            if websocket.application_state != WebSocketState.DISCONNECTED:
                with contextlib.suppress(Exception):
                    await websocket.close(code=relay.close_code or 1000)
    finally:
        connection.close()


class _Relay:
    def __init__(
        self,
        websocket: WebSocket,
        upstream: Upstream,
        session: _Session,
        robot_id: str,
        namespace: str,
    ) -> None:
        self.websocket = websocket
        self.upstream = upstream
        self.session = session
        self.robot_id = robot_id
        self.namespace = namespace
        self.close_code: int | None = None
        self._denied_audited: dict[tuple[str, str, str], float] = {}

    async def run(self) -> None:
        tasks = [
            asyncio.create_task(self._from_client()),
            asyncio.create_task(self._from_robot()),
            asyncio.create_task(self._watch_session()),
        ]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    async def _watch_session(self) -> None:
        """End the socket when its session does, even if the browser is silent."""
        while True:
            await asyncio.sleep(SESSION_CHECK_S)
            # A command may just have looked; no need to touch the session twice.
            if self.session.stale() and not self._refresh():
                return

    async def _from_robot(self) -> None:
        with contextlib.suppress(ConnectionClosed, WebSocketDisconnect):
            while True:
                message = await self.upstream.recv()
                if isinstance(message, bytes):
                    await self.websocket.send_bytes(message)
                else:
                    await self.websocket.send_text(message)

    async def _from_client(self) -> None:
        with contextlib.suppress(WebSocketDisconnect, ConnectionClosed):
            while True:
                message = await self.websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                text = message.get("text")
                if text is None:
                    await self.websocket.send_text(_refusal(None, "binary frames are not accepted"))
                    continue
                if not await self._handle(text):
                    return

    async def _handle(self, text: str) -> bool:
        """Check one frame; forward or refuse it. False ends the connection."""
        try:
            frame = json.loads(text)
        except (ValueError, RecursionError):
            # RecursionError: a message nested deeper than the parser allows.
            await self.websocket.send_text(_refusal(None, "not JSON"))
            return True

        if self.session.stale() and not self._refresh():
            return False
        principal = self.session.principal
        assert principal is not None  # noqa: S101 — _refresh guarantees it
        decision = decide(frame, principal.role or "", self.namespace)
        if decision.audit:
            # A command: decide on who the caller is now, not a minute ago.
            if not self._refresh():
                return False
            principal = self.session.principal
            assert principal is not None  # noqa: S101
            decision = decide(frame, principal.role or "", self.namespace)
            self._audit(frame, decision, principal)

        if decision.allow:
            # What was checked is what is sent: the parsed frame, serialised
            # again, not the original text (whose duplicate keys or odd
            # encodings another JSON parser might read differently).
            try:
                checked = json.dumps(frame, allow_nan=False, separators=(",", ":"))
            except ValueError:
                await self.websocket.send_text(_refusal(frame, "non-finite number"))
                return True
            await self.upstream.send(checked)
        else:
            await self.websocket.send_text(_refusal(frame, decision.reason))
        return True

    def _refresh(self) -> bool:
        principal = self.session.resolve()
        if principal is None:
            self.close_code = CLOSE_UNAUTHENTICATED
            return False
        if principal.must_change_password:
            self.close_code = CLOSE_FORBIDDEN
            return False
        return True

    def _audit(self, frame: dict, decision: Decision, principal: auth.Principal) -> None:
        op = str(frame.get("op"))[:40]
        target = _target(frame)
        if not decision.allow:
            key = (op, target, decision.reason)
            now = time.monotonic()
            if now - self._denied_audited.get(key, -DENIED_AUDIT_EVERY_S) < DENIED_AUDIT_EVERY_S:
                return
            self._denied_audited[key] = now
        path = f"/api/robots/{self.robot_id}/ros {op} {target}"
        try:
            audit_repo.record(
                self.session.connection,
                {
                    "user_id": principal.user_id,
                    "username": principal.username,
                    "role": principal.role,
                    "action": f"WS {path}",
                    "method": "WS",
                    "path": path,
                    "status": 200 if decision.allow else 403,
                    "detail": None if decision.allow else decision.reason,
                    "ip": client_ip(self.websocket),
                },
            )
        except sqlite3.Error:
            log.exception("Could not write audit record for %s", path)
