"""
The rosbridge relay, end to end against a fake robot.

The fake stands in for rosbridge: it records every frame that reaches it and
echoes each one back, so a test can tell "forwarded" from "refused" by what
arrives next on the browser's side.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import ros_proxy
from app.auth import SESSION_COOKIE
from app.config import Settings
from app.db import connect
from app.repositories import users as users_repo
from app.security import hash_token

ORIGIN = {"origin": "http://localhost:3100"}

GOAL = {
    "op": "publish",
    "id": "publish:/goal_pose:7",
    "topic": "/goal_pose",
    "msg": {
        "header": {"frame_id": "map", "stamp": {"sec": 0, "nanosec": 0}},
        "pose": {"position": {"x": 1.5, "y": -2.0, "z": 0}, "orientation": {"w": 1.0}},
    },
    "latch": False,
}


class FakeUpstream:
    def __init__(self, robot: FakeRobot) -> None:
        self.robot = robot
        self.queue: asyncio.Queue[str | bytes] = asyncio.Queue()
        for frame in robot.greeting:
            self.queue.put_nowait(frame)

    async def send(self, message: str) -> None:
        frame = json.loads(message)
        self.robot.raw.append(message)
        self.robot.received.append(frame)
        await self.queue.put(json.dumps({"op": "echo", "frame": frame}))

    async def recv(self) -> str | bytes:
        return await self.queue.get()

    async def close(self) -> None:
        self.robot.closed += 1


class FakeRobot:
    """Injected as app.state.ros_connect."""

    def __init__(self) -> None:
        self.greeting: list[str | bytes] = []
        self.received: list[dict] = []
        self.raw: list[str] = []
        self.urls: list[str] = []
        self.closed = 0

    async def __call__(self, url: str) -> FakeUpstream:
        self.urls.append(url)
        return FakeUpstream(self)


@pytest.fixture
def robot(anon_client: TestClient) -> FakeRobot:
    fake = FakeRobot()
    anon_client.app.state.ros_connect = fake  # type: ignore[attr-defined]
    return fake


@pytest.fixture
def robot_id(client: TestClient, robot_payload: dict) -> str:
    response = client.post("/api/robots", json=robot_payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def audit_rows(settings: Settings) -> list[dict]:
    conn = connect(settings.db_path)
    try:
        rows = conn.execute(
            "SELECT username, role, method, path, status, detail FROM audit_log "
            "WHERE method = 'WS' ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def close_code(action: Callable[[], object]) -> int:
    with pytest.raises(WebSocketDisconnect) as caught:
        action()
    return caught.value.code


def expect_ready(ws) -> None:
    """The relay's first frame once the robot's rosbridge has answered."""
    assert ws.receive_json() == json.loads(ros_proxy.READY_FRAME)


# ── handshake ────────────────────────────────────────────────────────────────


def test_no_cookie_is_closed_4401(anon_client: TestClient, robot: FakeRobot, robot_id: str) -> None:
    with anon_client.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        assert close_code(ws.receive_text) == 4401
    assert robot.urls == []


@pytest.mark.parametrize("headers", [{}, {"origin": "http://evil.example"}, {"origin": "null"}])
def test_foreign_origin_is_refused(
    client_as, robot: FakeRobot, robot_id: str, headers: dict
) -> None:
    operator = client_as("operator")
    with (
        pytest.raises(WebSocketDisconnect) as caught,
        operator.websocket_connect(f"/api/robots/{robot_id}/ros", headers=headers),
    ):
        pass
    assert caught.value.code == 4403
    assert robot.urls == []


def test_same_host_origin_is_accepted(client_as, robot: FakeRobot, robot_id: str) -> None:
    viewer = client_as("viewer")
    headers = {"origin": "http://testserver"}
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=headers) as ws:
        expect_ready(ws)
        ws.send_text(json.dumps({"op": "subscribe", "topic": "/map"}))
        assert ws.receive_json()["op"] == "echo"


def test_must_change_password_is_closed_4403(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str
) -> None:
    pending = client_as("operator")
    conn = connect(settings.db_path)
    try:
        conn.execute(
            "UPDATE users SET must_change_password = 1 WHERE id = ?", (pending.user["id"],)
        )
    finally:
        conn.close()
    with pending.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        assert close_code(ws.receive_text) == 4403
    assert robot.urls == []


def test_unknown_robot_is_closed_4404(client_as, robot: FakeRobot) -> None:
    viewer = client_as("viewer")
    with viewer.websocket_connect("/api/robots/nope/ros", headers=ORIGIN) as ws:
        assert close_code(ws.receive_text) == 4404


def test_unreachable_robot_is_closed_1011(
    client_as, anon_client: TestClient, robot_id: str
) -> None:
    async def refuse(url: str):
        raise OSError("connection refused")

    anon_client.app.state.ros_connect = refuse  # type: ignore[attr-defined]
    viewer = client_as("viewer")
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        assert close_code(ws.receive_text) == 1011


def test_ready_is_sent_only_once_the_robot_answers(
    client_as, robot: FakeRobot, robot_id: str
) -> None:
    """The browser's socket opens before the robot is reached; "ready" is the
    only sign the robot answered, and nothing from the robot precedes it."""
    robot.greeting.append(json.dumps({"op": "publish", "topic": "/robot_status", "msg": {}}))
    viewer = client_as("viewer")
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        first = ws.receive_json()
        assert first == {"op": "status", "level": "info", "msg": ros_proxy.READY_MESSAGE}
        assert "id" not in first  # roslib passes id-less status frames on as `status`
        assert ws.receive_json()["topic"] == "/robot_status"


def test_connects_to_the_registered_bridge(client_as, robot: FakeRobot, robot_id: str) -> None:
    viewer = client_as("viewer")
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text(json.dumps({"op": "subscribe", "topic": "/robot_status"}))
        ws.receive_json()
    assert robot.urls == ["ws://192.168.1.50:8765"]


# ── commands ─────────────────────────────────────────────────────────────────


def test_operator_goal_is_forwarded_and_audited(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str
) -> None:
    operator = client_as("operator", "olivia")
    with operator.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text(json.dumps(GOAL))
        echoed = ws.receive_json()
    assert echoed == {"op": "echo", "frame": GOAL}
    assert robot.received == [GOAL]
    [row] = audit_rows(settings)
    assert row["username"] == "olivia"
    assert row["role"] == "operator"
    assert row["status"] == 200
    assert row["path"] == f"/api/robots/{robot_id}/ros publish /goal_pose"


def test_viewer_goal_is_refused_not_forwarded_and_audited(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str
) -> None:
    viewer = client_as("viewer", "victor")
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text(json.dumps(GOAL))
        refusal = ws.receive_json()
        # A frame sent afterwards still flows: the connection survives a refusal.
        ws.send_text(json.dumps({"op": "subscribe", "topic": "/map"}))
        after = ws.receive_json()
    assert refusal["op"] == "status"
    assert refusal["level"] == "error"
    assert refusal["id"] == GOAL["id"]
    assert refusal["msg"].startswith("forbidden:")
    assert after["op"] == "echo"
    assert all(frame["op"] != "publish" for frame in robot.received)
    [row] = audit_rows(settings)
    assert (row["username"], row["status"]) == ("victor", 403)


def test_refused_service_call_gets_a_failed_service_response(
    client_as, robot: FakeRobot, robot_id: str
) -> None:
    viewer = client_as("viewer")
    frame = {
        "op": "call_service",
        "id": "call_service:/robot_mode:3",
        "service": "/robot_mode",
        "type": "custom_interfaces/srv/RobotMode",
        "args": {"robot_mode": "map"},
    }
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text(json.dumps(frame))
        response = ws.receive_json()
    assert response == {
        "op": "service_response",
        "id": frame["id"],
        "service": "/robot_mode",
        "result": False,
        "values": response["values"],
    }
    assert response["values"].startswith("forbidden:")
    assert robot.received == []


def test_viewer_may_stop(client_as, robot: FakeRobot, robot_id: str) -> None:
    viewer = client_as("viewer")
    frame = {
        "op": "call_service",
        "id": "c1",
        "service": "/robot_mode",
        "args": {"robot_mode": "stop"},
    }
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text(json.dumps(frame))
        assert ws.receive_json()["op"] == "echo"
    assert robot.received == [frame]


def test_viewer_drive_is_refused_but_zero_twist_passes(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str
) -> None:
    viewer = client_as("viewer")

    def teleop(x: float) -> str:
        return json.dumps(
            {
                "op": "publish",
                "topic": "/teleop/cmd_vel",
                "msg": {"linear": {"x": x, "y": 0, "z": 0}, "angular": {"x": 0, "y": 0, "z": 0}},
            }
        )

    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text(teleop(0.5))
        assert ws.receive_json()["op"] == "status"
        ws.send_text(teleop(0))
        assert ws.receive_json()["op"] == "echo"
    assert len(robot.received) == 1
    # Teleop is a stream, not audited.
    assert audit_rows(settings) == []


def test_garbage_is_refused(client_as, robot: FakeRobot, robot_id: str) -> None:
    operator = client_as("operator")
    with operator.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text("{not json")
        assert ws.receive_json()["msg"].startswith("forbidden:")
        ws.send_bytes(b"\x81\x00")
        assert ws.receive_json()["msg"].startswith("forbidden:")
        ws.send_text(json.dumps({"op": "send_action_goal", "action": "/navigate_to_pose"}))
        assert ws.receive_json()["msg"].startswith("forbidden:")
    assert robot.received == []


# ── robot to browser ─────────────────────────────────────────────────────────


def test_large_frames_from_the_robot_are_relayed(
    client_as, robot: FakeRobot, robot_id: str
) -> None:
    big = json.dumps({"op": "publish", "topic": "/map", "msg": {"data": "x" * (5 * 2**20)}})
    robot.greeting = [big]
    viewer = client_as("viewer")
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        assert ws.receive_text() == big


# ── session lifetime ─────────────────────────────────────────────────────────


def test_signed_out_mid_stream_is_closed_on_next_command(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str
) -> None:
    operator = client_as("operator")
    with operator.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text(json.dumps(GOAL))
        assert ws.receive_json()["op"] == "echo"

        conn = connect(settings.db_path)
        try:
            users_repo.delete_session(conn, hash_token(operator.cookies[SESSION_COOKIE]))
        finally:
            conn.close()

        ws.send_text(json.dumps(GOAL))
        assert close_code(ws.receive_text) == 4401
    assert len(robot.received) == 1
    assert robot.closed == 1


def test_demoted_mid_stream_is_refused_on_next_command(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str
) -> None:
    operator = client_as("operator")
    with operator.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        conn = connect(settings.db_path)
        try:
            conn.execute("UPDATE users SET role = 'viewer' WHERE id = ?", (operator.user["id"],))
        finally:
            conn.close()
        ws.send_text(json.dumps(GOAL))
        assert ws.receive_json()["op"] == "status"
    assert robot.received == []


def _sign_out(settings: Settings, test_client: TestClient) -> None:
    conn = connect(settings.db_path)
    try:
        users_repo.delete_session(conn, hash_token(test_client.cookies[SESSION_COOKIE]))
    finally:
        conn.close()


def test_silent_socket_is_closed_when_signed_out(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str, monkeypatch
) -> None:
    # A page that only watches telemetry sends nothing; the watchdog must still
    # notice the session is gone.
    monkeypatch.setattr(ros_proxy, "SESSION_CHECK_S", 0.05)
    monkeypatch.setattr(ros_proxy, "RESOLVE_EVERY_S", 0.0)
    viewer = client_as("viewer")
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        _sign_out(settings, viewer)
        assert close_code(ws.receive_text) == 4401
    assert robot.received == []


def test_silent_socket_is_closed_when_password_must_change(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str, monkeypatch
) -> None:
    monkeypatch.setattr(ros_proxy, "SESSION_CHECK_S", 0.05)
    monkeypatch.setattr(ros_proxy, "RESOLVE_EVERY_S", 0.0)
    viewer = client_as("viewer")
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        conn = connect(settings.db_path)
        try:
            conn.execute(
                "UPDATE users SET must_change_password = 1 WHERE id = ?", (viewer.user["id"],)
            )
        finally:
            conn.close()
        assert close_code(ws.receive_text) == 4403


def test_teleop_after_sign_out_is_cut_once_the_session_is_stale(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str, monkeypatch
) -> None:
    # Watchdog out of the way: this is the per-frame staleness check.
    monkeypatch.setattr(ros_proxy, "SESSION_CHECK_S", 3600.0)
    monkeypatch.setattr(ros_proxy, "RESOLVE_EVERY_S", 0.0)
    operator = client_as("operator")
    drive = json.dumps(
        {
            "op": "publish",
            "topic": "/teleop/cmd_vel",
            "msg": {"linear": {"x": 0.4, "y": 0, "z": 0}, "angular": {"x": 0, "y": 0, "z": 0}},
        }
    )
    with operator.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text(drive)
        assert ws.receive_json()["op"] == "echo"
        _sign_out(settings, operator)
        ws.send_text(drive)
        assert close_code(ws.receive_text) == 4401
    assert len(robot.received) == 1


def test_teleop_between_checks_does_not_touch_the_session(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str, monkeypatch
) -> None:
    # Within the staleness window the cached role decides: no database read.
    monkeypatch.setattr(ros_proxy, "SESSION_CHECK_S", 3600.0)
    monkeypatch.setattr(ros_proxy, "RESOLVE_EVERY_S", 3600.0)
    calls = []
    original = ros_proxy._Session.resolve

    def counting(self):
        calls.append(1)
        return original(self)

    monkeypatch.setattr(ros_proxy._Session, "resolve", counting)
    operator = client_as("operator")
    zero = {"linear": {"x": 0, "y": 0, "z": 0}, "angular": {"x": 0, "y": 0, "z": 0}}
    with operator.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        for _ in range(20):
            ws.send_text(json.dumps({"op": "publish", "topic": "/teleop/cmd_vel", "msg": zero}))
            ws.receive_json()
    assert len(calls) == 1  # the handshake


def test_forwards_the_checked_frame_not_the_original_text(
    client_as, robot: FakeRobot, robot_id: str
) -> None:
    viewer = client_as("viewer")
    # Duplicate keys: this parser keeps the last; whatever the robot's parser
    # would have done, it now receives exactly the frame that was judged.
    text = (
        '{ "op": "publish", "topic": "/teleop/cmd_vel",'
        ' "msg": {"linear": {"x": 9}}, "msg": {"linear": {"x": 0}} }'
    )
    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text(text)
        assert ws.receive_json()["op"] == "echo"
    assert robot.raw == ['{"op":"publish","topic":"/teleop/cmd_vel","msg":{"linear":{"x":0}}}']


def test_huge_numbers_are_refused_and_the_relay_survives(
    client_as, robot: FakeRobot, robot_id: str
) -> None:
    operator = client_as("operator")
    huge = "1" + "0" * 400
    with operator.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        ws.send_text(
            '{"op":"publish","topic":"/teleop/cmd_vel","msg":{"linear":{"x":' + huge + "}}}"
        )
        assert ws.receive_json()["msg"].startswith("forbidden:")
        ws.send_text(
            '{"op":"publish","topic":"/goal_pose","msg":{"pose":{"position":{"x":' + huge + "}}}}"
        )
        assert ws.receive_json()["msg"].startswith("forbidden:")
        ws.send_text(json.dumps({"op": "subscribe", "topic": "/map"}))
        assert ws.receive_json()["op"] == "echo"
    assert [frame["op"] for frame in robot.received] == ["subscribe"]


def test_refusals_with_different_reasons_are_each_audited_once(
    client_as, settings: Settings, robot: FakeRobot, robot_id: str
) -> None:
    viewer = client_as("viewer")

    def mode(value: str) -> str:
        return json.dumps(
            {
                "op": "call_service",
                "id": "c",
                "service": "/robot_mode",
                "args": {"robot_mode": value},
            }
        )

    with viewer.websocket_connect(f"/api/robots/{robot_id}/ros", headers=ORIGIN) as ws:
        expect_ready(ws)
        for value in ("nav", "map", "nav", "map", "nav"):
            ws.send_text(mode(value))
            assert ws.receive_json()["result"] is False
    rows = audit_rows(settings)
    assert len(rows) == 2
    assert {row["status"] for row in rows} == {403}
    assert len({row["detail"] for row in rows}) == 2


@pytest.mark.parametrize(
    ("base", "origin", "accepted"),
    [
        ("wss://testserver", "https://testserver", True),
        ("wss://testserver", "http://testserver", False),
        ("ws://testserver", "http://testserver", True),
        # TLS ended at a proxy the backend cannot trust: either scheme passes.
        ("ws://testserver", "https://testserver", True),
        ("ws://testserver", "ftp://testserver", False),
        ("ws://testserver", "http://testserver:8080", False),
    ],
)
def test_same_host_origin_scheme(
    client_as, robot: FakeRobot, robot_id: str, base: str, origin: str, accepted: bool
) -> None:
    viewer = client_as("viewer")
    url = f"{base}/api/robots/{robot_id}/ros"
    if accepted:
        with viewer.websocket_connect(url, headers={"origin": origin}) as ws:
            expect_ready(ws)
            ws.send_text(json.dumps({"op": "subscribe", "topic": "/map"}))
            assert ws.receive_json()["op"] == "echo"
    else:
        with (
            pytest.raises(WebSocketDisconnect) as caught,
            viewer.websocket_connect(url, headers={"origin": origin}),
        ):
            pass
        assert caught.value.code == 4403
