"""ChildGroups: stacks a previous agent left running are found and stopped, and nothing else is."""

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import child_groups  # noqa: E402
from child_groups import ChildGroups, group_alive, start_ticks, stop_group  # noqa: E402

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="reads /proc and signals process groups"
)

FAST = ((signal.SIGINT, 1.0), (signal.SIGTERM, 1.0))


def fast_stop(pgid):
    return stop_group(pgid, steps=FAST, kill_wait=3.0)


def spawn(script: str) -> subprocess.Popen:
    """A shell in a session of its own, as the agent starts its stacks."""
    return subprocess.Popen(["sh", "-c", script], start_new_session=True)


@pytest.fixture
def started():
    procs = []

    def start(script: str) -> subprocess.Popen:
        proc = spawn(script)
        procs.append(proc)
        # Long enough for the shell to have started what it runs.
        time.sleep(0.3)
        return proc

    yield start
    for proc in procs:
        stop_group(proc.pid, steps=((signal.SIGKILL, 1.0),), kill_wait=1.0)
        proc.wait(timeout=5)


def test_stopping_a_group_stops_its_children_too(started):
    proc = started("sleep 60 & sleep 60")
    assert fast_stop(proc.pid) == "stopped"
    assert not group_alive(proc.pid)


def test_children_left_behind_by_a_leader_that_exited_are_stopped(started):
    # ros2 launch exiting first used to leave its nodes running: the stop
    # looked at the launch process only and saw nothing left to do.
    proc = started("sleep 60 & exit 0")
    proc.wait(timeout=5)
    assert group_alive(proc.pid)
    assert fast_stop(proc.pid) == "stopped"
    assert not group_alive(proc.pid)


def test_a_group_that_ignores_the_polite_signals_is_killed(started):
    proc = started("trap '' INT TERM; sleep 60 & wait")
    assert fast_stop(proc.pid) == "killed"
    assert not group_alive(proc.pid)


def test_nothing_to_stop_is_reported_as_gone(started):
    proc = started("exit 0")
    proc.wait(timeout=5)
    assert fast_stop(proc.pid) == "gone"


def test_a_recorded_group_still_running_is_a_leftover_and_is_stopped(tmp_path, started):
    proc = started("sleep 60 & sleep 60")
    ChildGroups(tmp_path).record("launch", proc.pid)

    # The next agent, starting up.
    groups = ChildGroups(tmp_path)
    assert groups.leftovers() == {"launch": proc.pid}
    assert groups.stop_leftovers(stop=fast_stop) == {"launch": "stopped"}
    assert not group_alive(proc.pid)
    assert groups.leftovers() == {}


def test_a_leftover_whose_leader_exited_is_still_stopped(tmp_path, started):
    proc = started("sleep 60 & exit 0")
    ChildGroups(tmp_path).record("launch", proc.pid)
    proc.wait(timeout=5)
    assert ChildGroups(tmp_path).stop_leftovers(stop=fast_stop) == {"launch": "stopped"}
    assert not group_alive(proc.pid)


def test_a_group_stopped_cleanly_is_no_leftover(tmp_path, started):
    proc = started("sleep 60")
    groups = ChildGroups(tmp_path)
    groups.record("launch", proc.pid)
    fast_stop(proc.pid)
    groups.forget("launch")
    assert groups.leftovers() == {}


def test_a_reused_process_id_is_never_signalled(tmp_path, started):
    # The recorded process is gone and some other program got its number: its
    # start time gives it away, and it is left alone.
    proc = started("sleep 60")
    ChildGroups(tmp_path).record("launch", proc.pid)
    record = tmp_path / child_groups.RECORD_NAME
    entries = json.loads(record.read_text())
    entries["launch"]["start"] = start_ticks(proc.pid) - 1
    record.write_text(json.dumps(entries))

    stopped = []
    assert ChildGroups(tmp_path).stop_leftovers(stop=stopped.append) == {}
    assert stopped == []
    assert group_alive(proc.pid)


def test_a_group_recorded_in_another_boot_is_ignored(tmp_path, started):
    proc = started("sleep 60")
    ChildGroups(tmp_path).record("launch", proc.pid)
    record = tmp_path / child_groups.RECORD_NAME
    entries = json.loads(record.read_text())
    entries["launch"]["boot"] = "some-other-boot"
    record.write_text(json.dumps(entries))
    assert ChildGroups(tmp_path).leftovers() == {}


def test_the_record_is_cleared_once_leftovers_were_handled(tmp_path, started):
    proc = started("sleep 60")
    ChildGroups(tmp_path).record("launch", proc.pid)
    ChildGroups(tmp_path).stop_leftovers(stop=lambda pgid: "stuck")
    # Reported once, not on every start from now on.
    assert json.loads((tmp_path / child_groups.RECORD_NAME).read_text()) == {}


@pytest.mark.parametrize(
    "content",
    ["not json", "[1, 2]", json.dumps({"launch": "x"}), json.dumps({"launch": {"pgid": 1}})],
)
def test_an_unusable_record_signals_nothing(tmp_path, content):
    (tmp_path / child_groups.RECORD_NAME).write_text(content)
    stopped = []
    assert ChildGroups(tmp_path).stop_leftovers(stop=stopped.append) == {}
    assert stopped == []


def test_no_record_at_all_is_nothing_to_do(tmp_path):
    assert ChildGroups(tmp_path).leftovers() == {}
