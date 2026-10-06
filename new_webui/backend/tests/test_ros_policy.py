"""
The rosbridge allow-list, rule by rule.

Each rule is tested from both sides: the frame the web UI really sends gets
through for the role that may send it, and the nearest thing that must not get
through is refused.
"""

from __future__ import annotations

import pytest

from app.ros_policy import decide, ros_name

ROLES = ("viewer", "operator", "admin", "super_admin")


def twist(lx: float = 0, az: float = 0) -> dict:
    return {"linear": {"x": lx, "y": 0, "z": 0}, "angular": {"x": 0, "y": 0, "z": az}}


def publish(topic: str, msg: object) -> dict:
    return {"op": "publish", "id": "publish:1", "topic": topic, "msg": msg, "latch": False}


def call(service: str, args: object, frame_id: str = "call_service:1") -> dict:
    return {"op": "call_service", "id": frame_id, "service": service, "type": "x", "args": args}


GOAL = {
    "header": {"frame_id": "map", "stamp": {"sec": 0, "nanosec": 0}},
    "pose": {"position": {"x": 1.0, "y": 2.0, "z": 0}, "orientation": {"w": 1.0}},
}


# ── subscribe ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("topic", ["/robot_status", "/map", "/tf", "/global_costmap/costmap"])
def test_any_role_may_subscribe_to_status_topics(role: str, topic: str) -> None:
    frame = {
        "op": "subscribe",
        "id": "subscribe:1",
        "topic": topic,
        "type": "x",
        "throttle_rate": 0,
        "queue_length": 1,
        "compression": "png",
    }
    assert decide(frame, role, "").allow


def test_latched_subscribe_with_qos_is_allowed() -> None:
    frame = {"op": "subscribe", "topic": "/tf_static", "type": "x", "qos": {"depth": 1}}
    assert decide(frame, "viewer", "").allow


def test_subscribe_outside_the_list_is_refused() -> None:
    assert not decide({"op": "subscribe", "topic": "/cmd_vel"}, "super_admin", "").allow


@pytest.mark.parametrize("compression", ["cbor", "cbor-raw", "zip"])
def test_cbor_compression_is_refused(compression: str) -> None:
    frame = {"op": "subscribe", "topic": "/map", "compression": compression}
    decision = decide(frame, "super_admin", "")
    assert not decision.allow
    assert "compression" in decision.reason


def test_subscribe_with_unexpected_fields_is_refused() -> None:
    frame = {"op": "subscribe", "topic": "/map", "fragment_size": 10}
    assert not decide(frame, "super_admin", "").allow


def test_unsubscribe_and_unadvertise_are_always_allowed() -> None:
    assert decide({"op": "unsubscribe", "topic": "/anything"}, "viewer", "").allow
    assert decide({"op": "unadvertise", "topic": "/anything"}, "viewer", "").allow


# ── namespaces ───────────────────────────────────────────────────────────────


def test_namespace_is_applied_like_the_frontend() -> None:
    assert ros_name("amr_01", "/map") == "/amr_01/map"
    assert ros_name("/amr_01/", "/map") == "/amr_01/map"
    assert ros_name("amr_01", "/tf") == "/tf"
    assert ros_name("", "/map") == "/map"


def test_namespaced_robot_needs_namespaced_names() -> None:
    assert decide({"op": "subscribe", "topic": "/amr_01/map"}, "viewer", "amr_01").allow
    assert decide({"op": "subscribe", "topic": "/tf"}, "viewer", "amr_01").allow
    assert not decide({"op": "subscribe", "topic": "/map"}, "viewer", "amr_01").allow
    assert decide(publish("/amr_01/goal_pose", GOAL), "operator", "amr_01").allow
    assert not decide(publish("/goal_pose", GOAL), "operator", "amr_01").allow


# ── advertise ────────────────────────────────────────────────────────────────


def advertise(topic: str, message_type: str) -> dict:
    return {
        "op": "advertise",
        "id": "advertise:1",
        "topic": topic,
        "type": message_type,
        "latch": False,
        "queue_size": 100,
    }


@pytest.mark.parametrize("role", ROLES)
def test_any_role_may_advertise_teleop(role: str) -> None:
    assert decide(advertise("/teleop/cmd_vel", "geometry_msgs/msg/Twist"), role, "").allow


def test_teleop_must_be_advertised_as_twist() -> None:
    frame = advertise("/teleop/cmd_vel", "geometry_msgs/msg/TwistStamped")
    assert not decide(frame, "super_admin", "").allow


def test_goal_and_initial_pose_advertise_need_operator() -> None:
    goal = advertise("/goal_pose", "geometry_msgs/msg/PoseStamped")
    initial = advertise("/initialpose", "geometry_msgs/msg/PoseWithCovarianceStamped")
    assert not decide(goal, "viewer", "").allow
    assert not decide(initial, "viewer", "").allow
    assert decide(goal, "operator", "").allow
    assert decide(initial, "operator", "").allow


def test_raw_cmd_vel_cannot_be_advertised() -> None:
    frame = advertise("/cmd_vel", "geometry_msgs/msg/Twist")
    assert not decide(frame, "super_admin", "").allow


def test_latched_advertise_is_refused() -> None:
    frame = advertise("/teleop/cmd_vel", "geometry_msgs/msg/Twist") | {"latch": True}
    assert not decide(frame, "super_admin", "").allow


# ── publish: teleop ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", ROLES)
def test_any_role_may_send_a_zero_twist(role: str) -> None:
    assert decide(publish("/teleop/cmd_vel", twist()), role, "").allow


def test_viewer_cannot_drive() -> None:
    decision = decide(publish("/teleop/cmd_vel", twist(lx=0.3)), "viewer", "")
    assert not decision.allow
    assert "operator" in decision.reason
    assert not decide(publish("/teleop/cmd_vel", twist(az=-0.1)), "viewer", "").allow


def test_operator_can_drive() -> None:
    decision = decide(publish("/teleop/cmd_vel", twist(lx=0.3, az=0.5)), "operator", "")
    assert decision.allow
    # Teleop is a stream, not a command: never a database write per frame.
    assert not decision.audit


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_twist_is_refused(value: float) -> None:
    assert not decide(publish("/teleop/cmd_vel", twist(lx=value)), "super_admin", "").allow


@pytest.mark.parametrize(
    "msg",
    [
        None,
        "go",
        {"linear": {"x": "1"}},
        {"linear": {"x": True}},
        {"linear": {"x": 0, "w": 1}},
        {"linear": {"x": 0}, "extra": 1},
    ],
)
def test_malformed_twist_is_refused(msg: object) -> None:
    assert not decide(publish("/teleop/cmd_vel", msg), "super_admin", "").allow


def test_raw_cmd_vel_is_refused_even_for_a_zero_twist() -> None:
    assert not decide(publish("/cmd_vel", twist()), "super_admin", "").allow
    assert not decide(publish("/cmd_vel", twist(lx=1)), "super_admin", "").allow


def test_latched_publish_is_refused() -> None:
    frame = publish("/teleop/cmd_vel", twist()) | {"latch": True}
    assert not decide(frame, "super_admin", "").allow


# ── publish: goals ───────────────────────────────────────────────────────────


def test_operator_goal_is_allowed_and_audited() -> None:
    decision = decide(publish("/goal_pose", GOAL), "operator", "")
    assert decision.allow
    assert decision.audit


def test_viewer_goal_is_refused_and_audited() -> None:
    decision = decide(publish("/goal_pose", GOAL), "viewer", "")
    assert not decision.allow
    assert decision.audit


def test_initial_pose_needs_operator() -> None:
    msg = {"header": {}, "pose": {"pose": {}, "covariance": [0.0] * 36}}
    assert not decide(publish("/initialpose", msg), "viewer", "").allow
    assert decide(publish("/initialpose", msg), "admin", "").allow


def test_goal_with_nan_is_refused() -> None:
    msg = {"pose": {"position": {"x": float("nan")}}}
    assert not decide(publish("/goal_pose", msg), "super_admin", "").allow


# ── call_service ─────────────────────────────────────────────────────────────


CANCEL = "/navigate_to_pose/_action/cancel_goal"


@pytest.mark.parametrize("role", ROLES)
def test_anyone_may_cancel_navigation(role: str) -> None:
    decision = decide(call(CANCEL, {"goal_info": {"goal_id": {"uuid": [0] * 16}}}), role, "")
    assert decision.allow
    assert decision.audit


@pytest.mark.parametrize("role", ROLES)
def test_anyone_may_stop(role: str) -> None:
    decision = decide(call("/robot_mode", {"robot_mode": "stop"}), role, "")
    assert decision.allow
    assert decision.audit


def test_mapping_mode_needs_operator() -> None:
    assert not decide(call("/robot_mode", {"robot_mode": "map"}), "viewer", "").allow
    decision = decide(call("/robot_mode", {"robot_mode": "map"}), "operator", "")
    assert decision.allow
    assert decision.audit


@pytest.mark.parametrize(
    "args",
    [
        {"robot_mode": "nav"},
        {"robot_mode": "nav|/etc/passwd"},
        {"robot_mode": "stop", "extra": 1},
        {"robot_mode": 1},
        {},
        "stop",
    ],
)
def test_other_robot_modes_are_refused(args: object) -> None:
    decision = decide(call("/robot_mode", args), "super_admin", "")
    assert not decision.allow
    assert decision.audit


def test_map_save_needs_operator_and_a_plain_name() -> None:
    assert decide(call("/map_save", {"robot_mode": "Warehouse A_1.v2"}), "operator", "").allow
    assert not decide(call("/map_save", {"robot_mode": "Warehouse"}), "viewer", "").allow


@pytest.mark.parametrize(
    "name",
    [
        "",
        "a/b",
        "../etc",
        "x" * 65,
        "name;rm -rf",
        "a|b",
        3,
        None,
        "map\n",
        "map\nother",
        "a..b",
        "..",
        ".hidden",
        "   ",
    ],
)
def test_map_save_bad_names_are_refused(name: object) -> None:
    assert not decide(call("/map_save", {"robot_mode": name}), "super_admin", "").allow


def test_other_services_are_refused() -> None:
    for service in ("/map_server/load_map", "/slam_toolbox/save_map", "/dock_command", "/rosapi"):
        decision = decide(call(service, {}), "super_admin", "")
        assert not decision.allow
        assert decision.audit


# ── everything else ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "frame",
    [
        {"op": "send_action_goal", "action": "/navigate_to_pose", "args": {}},
        {"op": "set_level", "level": "none"},
        {"op": "advertise_service", "service": "/robot_mode", "type": "x"},
        {"op": "fragment", "id": "1", "data": "x", "num": 0, "total": 2},
        {"op": "auth", "mac": "x"},
        {"op": "png", "data": "x"},
        {"op": "whatever"},
        {"topic": "/map"},
        {"op": None},
    ],
)
def test_every_other_op_is_refused(frame: dict) -> None:
    assert not decide(frame, "super_admin", "").allow


@pytest.mark.parametrize("frame", [None, [], "subscribe", 3])
def test_non_objects_are_refused(frame: object) -> None:
    assert not decide(frame, "super_admin", "").allow  # type: ignore[arg-type]


def test_unknown_role_gets_only_what_viewers_get() -> None:
    assert not decide(publish("/goal_pose", GOAL), "", "").allow
    assert decide(publish("/teleop/cmd_vel", twist()), "", "").allow


# ── hostile numbers and shapes never raise ───────────────────────────────────

HUGE = 10**400


@pytest.mark.parametrize(
    "frame",
    [
        publish("/teleop/cmd_vel", twist(lx=HUGE)),
        publish("/teleop/cmd_vel", {"linear": {"x": -HUGE}}),
        publish("/goal_pose", {"pose": {"position": {"x": HUGE}}}),
        publish("/initialpose", {"pose": {"covariance": [HUGE] * 36}}),
        call(CANCEL, {"goal_info": {"stamp": {"sec": HUGE}}}),
        {"op": "subscribe", "topic": "/map", "throttle_rate": HUGE},
        {"op": "subscribe", "topic": "/map", "queue_length": -1},
        {"op": "subscribe", "topic": "/map", "throttle_rate": 1.5},
        {"op": "subscribe", "topic": "/map", "qos": {"depth": HUGE}},
        {"op": "subscribe", "topic": "/map", "compression": ["png"]},
        {"op": "subscribe", "topic": "/map", "compression": {"a": 1}},
        {"op": "publish", "topic": ["/teleop/cmd_vel"], "msg": twist()},
        {
            "op": "advertise",
            "topic": "/teleop/cmd_vel",
            "type": "geometry_msgs/msg/Twist",
            "queue_size": HUGE,
        },
        {"op": ["publish"]},
    ],
)
def test_hostile_values_are_refused_without_raising(frame: dict) -> None:
    decision = decide(frame, "super_admin", "")
    assert not decision.allow


def test_deeply_nested_message_is_refused_without_raising() -> None:
    msg: dict = {}
    inner = msg
    for _ in range(5000):
        inner["a"] = {}
        inner = inner["a"]
    assert not decide(publish("/goal_pose", msg), "super_admin", "").allow
