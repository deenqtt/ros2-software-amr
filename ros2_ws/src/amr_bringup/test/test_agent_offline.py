"""
The robot agent's behaviour when the server cannot be reached.

The agent imports rclpy and the ROS message packages at module level, which a
laptop without ROS does not have. They are replaced here by stand-ins: none of
the methods under test touch ROS, only the backend client and the disk.

Run with
    python3 -m pytest ros2_ws/src/amr_bringup/test/test_agent_offline.py
"""

import hashlib
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


class _Anything:
    """Stands in for any ROS class or constant the module touches on import."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return _Anything()

    def __call__(self, *args, **kwargs):
        return _Anything()


def _stub(name: str) -> None:
    module = types.ModuleType(name)
    module.__getattr__ = lambda attr: _Anything  # type: ignore[attr-defined]
    sys.modules[name] = module


for _name in (
    "rclpy",
    "rclpy.action",
    "rclpy.callback_groups",
    "rclpy.executors",
    "rclpy.node",
    "rclpy.qos",
    "action_msgs",
    "action_msgs.msg",
    "geometry_msgs",
    "geometry_msgs.msg",
    "std_msgs",
    "std_msgs.msg",
    "std_srvs",
    "std_srvs.srv",
    "nav2_msgs",
    "nav2_msgs.action",
    "nav2_msgs.srv",
    "custom_interfaces",
    "custom_interfaces.action",
    "custom_interfaces.srv",
):
    if _name not in sys.modules:
        _stub(_name)

import robot_agent_node as agent_module  # noqa: E402
from agent_state import AgentState  # noqa: E402
from backend_client import BackendError  # noqa: E402


class _Log:
    def __init__(self):
        self.lines = []

    def info(self, text):
        self.lines.append(("info", text))

    def warning(self, text):
        self.lines.append(("warning", text))

    def error(self, text):
        self.lines.append(("error", text))


class FakeBackend:
    """Records what the agent sent, and fails on demand."""

    def __init__(self):
        self.reports = []
        self.offline = False
        self.status_for = {}  # run_id -> HTTP status to fail with
        self.active_run = None
        self.robot = {"active_map_id": "m1", "desired_mode": "nav"}

    def report_run(self, run_id, patch):
        if self.offline:
            raise BackendError("connection refused", 0)
        if run_id in self.status_for:
            raise BackendError("refused", self.status_for[run_id])
        self.reports.append((run_id, dict(patch)))
        return {}

    def get_active_run(self):
        if self.offline:
            raise BackendError("connection refused", 0)
        return self.active_run

    def get_robot(self):
        if self.offline:
            raise BackendError("connection refused", 0)
        return self.robot


def make_agent(tmp_path, backend=None):
    """An agent object with only the state these methods use."""
    agent = agent_module.RobotAgent.__new__(agent_module.RobotAgent)
    log = _Log()
    agent.get_logger = lambda: log
    agent._log = log
    agent._backend = backend if backend is not None else FakeBackend()
    agent._backend_state = "unknown"
    agent._store = AgentState(tmp_path / "state")
    agent._cache_dir = tmp_path / "cache"
    agent._registry_desired = "nav"
    agent._offline_announced = False
    agent._station_poses = {}
    agent._current_map = "/default.yaml"
    agent._run_thread = None
    agent._mode = agent_module.MODE_NAV
    agent._state = agent_module.STATE_RUNNING
    agent._map_busy = __import__("threading").Lock()
    agent.reconciled = []
    agent._reconcile_mode = lambda desired, assigned: agent.reconciled.append((desired, assigned))
    agent.started_runs = []

    class _Thread:
        def __init__(self, target, args, daemon):
            agent.started_runs.append(args[0]["id"])

        def start(self):
            pass

    agent_module.threading.Thread = _Thread  # only _poll_run starts threads here
    return agent


@pytest.fixture(autouse=True)
def _restore_thread():
    import threading

    original = threading.Thread
    yield
    agent_module.threading.Thread = original


# ── Run reports ─────────────────────────────────────────────────────────────


def test_a_report_goes_straight_out_when_online(tmp_path):
    agent = make_agent(tmp_path)
    assert agent._report_run("r1", {"step_index": 0}) is True
    assert agent._backend.reports == [("r1", {"step_index": 0})]
    assert agent._store.pending() == []


def test_a_report_made_offline_is_kept_and_sent_later_in_order(tmp_path):
    agent = make_agent(tmp_path)
    agent._backend.offline = True

    agent._report_run("r1", {"step_index": 0})
    agent._report_run("r1", {"reached_lap": 1, "reached_index": 0})
    assert agent._backend.reports == []
    assert agent._store.pending_count() == 2

    agent._backend.offline = False
    # The next report must not overtake the two waiting ones.
    agent._report_run("r1", {"step_index": 1})

    assert agent._backend.reports == [
        ("r1", {"step_index": 0}),
        ("r1", {"reached_lap": 1, "reached_index": 0}),
        ("r1", {"step_index": 1}),
    ]
    assert agent._store.pending() == []


def test_an_offline_report_does_not_stop_the_run(tmp_path):
    # Ending a run because the network blinked would strand the robot.
    agent = make_agent(tmp_path)
    agent._backend.offline = True
    assert agent._report_run("r1", {"step_index": 0}) is True


def test_a_run_ended_on_the_server_stops_the_robot(tmp_path):
    agent = make_agent(tmp_path)
    agent._backend.status_for["r1"] = 409
    assert agent._report_run("r1", {"step_index": 1}) is False


def test_a_report_the_server_refuses_is_not_kept_forever(tmp_path):
    agent = make_agent(tmp_path)
    agent._backend.status_for["r1"] = 422
    assert agent._report_run("r1", {"step_index": 1}) is True
    assert agent._store.pending() == []


def test_a_final_report_is_remembered_even_when_it_cannot_be_sent(tmp_path):
    agent = make_agent(tmp_path)
    agent._backend.offline = True
    agent._report_run("r1", {"state": "done"})
    assert agent._store.finished("r1") == {"state": "done"}


# ── Never driving a finished run twice ──────────────────────────────────────


def test_a_run_finished_here_is_not_driven_again(tmp_path):
    """
    The bug this exists for: "done" was lost while offline, the run stayed
    live on the server, and on reconnect the robot drove the route again.
    """
    agent = make_agent(tmp_path)
    agent._store.mark_finished("r1", {"state": "done"})
    agent._backend.active_run = {"id": "r1", "steps": [{"station_id": "s1"}]}

    agent._poll_run()

    assert agent.started_runs == []
    # The server is told again instead.
    assert agent._backend.reports == [("r1", {"state": "done"})]


def test_waiting_reports_are_delivered_before_asking_for_work(tmp_path):
    agent = make_agent(tmp_path)
    agent._store.enqueue("r1", {"state": "done"})
    # By the time the server is asked, "done" has arrived; a real server would
    # then offer no run. This one still offers r1, which must be refused.
    agent._backend.active_run = {"id": "r1", "steps": [{"station_id": "s1"}]}
    agent._store.mark_finished("r1", {"state": "done"})

    agent._poll_run()

    assert agent._backend.reports[0] == ("r1", {"state": "done"})
    assert agent.started_runs == []


def test_no_new_run_starts_while_reports_are_still_waiting(tmp_path):
    agent = make_agent(tmp_path)
    agent._store.enqueue("r1", {"step_index": 2})
    agent._backend.status_for["r1"] = 503  # server up but failing
    agent._backend.active_run = {"id": "r2", "steps": [{"station_id": "s1"}]}

    agent._poll_run()

    assert agent.started_runs == []


def test_a_new_run_starts_normally(tmp_path):
    agent = make_agent(tmp_path)
    agent._backend.active_run = {"id": "r9", "steps": [{"station_id": "s1"}]}
    agent._poll_run()
    assert agent.started_runs == ["r9"]


# ── Booting without the server ──────────────────────────────────────────────


def _cache_map(agent, map_id="m1"):
    directory = agent._cache_dir / map_id
    directory.mkdir(parents=True)
    image = b"P5 2 2 255 abcd"
    (directory / "map.pgm").write_bytes(image)
    (directory / "map.yaml").write_text("image: map.pgm\n")
    return {
        "id": map_id,
        "yaml_file": "map.yaml",
        "image_file": "map.pgm",
        "content_hash": hashlib.sha256(image).hexdigest(),
    }


def test_an_offline_boot_starts_from_the_saved_registry(tmp_path):
    agent = make_agent(tmp_path)
    record = _cache_map(agent)
    agent._store.save_registry(active_map_id="m1", desired_mode="nav", map_record=record)
    agent._store.save_stations("m1", [{"id": "s1", "x": 1.0, "y": 2.0, "yaw": 0.5}])
    agent._backend.offline = True

    agent._sync_assigned_map()

    assert agent.reconciled == [(agent_module.MODE_NAV, "m1")]
    assert agent._current_map == str(agent._cache_dir / "m1" / "map.yaml")
    assert agent._station_poses == {"s1": (1.0, 2.0, 0.5)}


def test_an_offline_boot_refuses_a_cache_that_fails_its_hash(tmp_path):
    agent = make_agent(tmp_path)
    record = _cache_map(agent)
    record["content_hash"] = "not-the-hash"
    agent._store.save_registry(active_map_id="m1", desired_mode="nav", map_record=record)
    agent._backend.offline = True

    agent._sync_assigned_map()

    assert agent.reconciled == []
    # And the only copy there is was not deleted.
    assert (agent._cache_dir / "m1" / "map.pgm").is_file()


def test_nothing_happens_offline_without_a_saved_registry(tmp_path):
    agent = make_agent(tmp_path)
    agent._backend.offline = True
    agent._sync_assigned_map()
    assert agent.reconciled == []


def test_an_unregistered_robot_is_not_driven_from_the_snapshot(tmp_path):
    agent = make_agent(tmp_path)
    record = _cache_map(agent)
    agent._store.save_registry(active_map_id="m1", desired_mode="nav", map_record=record)

    class Gone(FakeBackend):
        def get_robot(self):
            raise BackendError("not found", 404)

    agent._backend = Gone()
    agent._sync_assigned_map()

    assert agent.reconciled == []


def test_the_saved_registry_follows_the_server_when_online(tmp_path):
    agent = make_agent(tmp_path)
    agent._backend.robot = {"active_map_id": None, "desired_mode": "idle"}

    agent._sync_assigned_map()

    saved = agent._store.load_registry()
    assert saved["desired_mode"] == "idle"
    assert saved["active_map_id"] is None
