"""
Tests for the robot agent's on-disk memory (scripts/agent_state.py).

Plain pytest, no ROS: run with
    python3 -m pytest ros2_ws/src/amr_bringup/test/test_agent_state.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from agent_state import AgentState  # noqa: E402


def test_registry_round_trips(tmp_path):
    state = AgentState(tmp_path)
    record = {"id": "m1", "yaml_file": "map.yaml", "image_file": "map.pgm", "content_hash": "abc"}

    state.save_registry(active_map_id="m1", desired_mode="nav", map_record=record)

    loaded = AgentState(tmp_path).load_registry()
    assert loaded["active_map_id"] == "m1"
    assert loaded["desired_mode"] == "nav"
    assert loaded["map_record"] == record


def test_registry_keeps_the_map_when_reread_without_it(tmp_path):
    state = AgentState(tmp_path)
    record = {"id": "m1", "content_hash": "abc"}
    state.save_registry(active_map_id="m1", desired_mode="nav", map_record=record)

    # Mode changed; the map was not re-read this time.
    state.save_registry(active_map_id="m1", desired_mode="idle")

    loaded = state.load_registry()
    assert loaded["desired_mode"] == "idle"
    assert loaded["map_record"] == record


def test_registry_drops_the_map_when_the_assignment_changes(tmp_path):
    state = AgentState(tmp_path)
    state.save_registry(active_map_id="m1", desired_mode="nav", map_record={"id": "m1"})

    state.save_registry(active_map_id="m2", desired_mode="nav")

    # A record for m1 must never be paired with an assignment to m2.
    assert state.load_registry()["map_record"] is None


def test_a_corrupt_file_reads_as_missing(tmp_path):
    (tmp_path / "registry.json").write_text("{not json")
    assert AgentState(tmp_path).load_registry() is None


def test_stations_are_kept_per_map(tmp_path):
    state = AgentState(tmp_path)
    state.save_stations("m1", [{"id": "s1", "x": 1.0, "y": 2.0, "yaw": 0.5}])

    assert AgentState(tmp_path).load_stations("m1")[0]["id"] == "s1"
    assert state.load_stations("m2") == []


def test_outbox_sends_in_order_and_stops_at_the_first_retry(tmp_path):
    state = AgentState(tmp_path)
    state.enqueue("r1", {"step_index": 0})
    state.enqueue("r1", {"reached_index": 0})
    state.enqueue("r1", {"state": "done"})

    sent = []

    def send(run_id, patch):
        if len(sent) == 2:
            return "retry"
        sent.append(patch)
        return "sent"

    removed, empty = state.flush(send)

    assert removed == 2
    assert not empty
    assert sent == [{"step_index": 0}, {"reached_index": 0}]
    # The one that could not go is still first in line, and survives a restart.
    assert [item["patch"] for item in AgentState(tmp_path).pending()] == [{"state": "done"}]


def test_outbox_drops_what_the_server_refuses_for_good(tmp_path):
    state = AgentState(tmp_path)
    state.enqueue("r1", {"step_index": 1})
    state.enqueue("r2", {"state": "done"})

    removed, empty = state.flush(lambda run_id, patch: "drop" if run_id == "r1" else "sent")

    assert removed == 2
    assert empty


def test_outbox_limit_never_drops_a_terminal_report(tmp_path, monkeypatch):
    import agent_state

    monkeypatch.setattr(agent_state, "OUTBOX_LIMIT", 3)
    state = AgentState(tmp_path)
    state.enqueue("r1", {"state": "done"})
    for index in range(5):
        state.enqueue("r2", {"step_index": index})

    patches = [item["patch"] for item in state.pending()]
    assert len(patches) == 3
    assert {"state": "done"} in patches
    # The newest progress is what is kept.
    assert patches[-1] == {"step_index": 4}


def test_has_pending_for_a_run(tmp_path):
    state = AgentState(tmp_path)
    state.enqueue("r1", {"step_index": 0})
    assert state.has_pending_for("r1")
    assert not state.has_pending_for("r2")


def test_a_finished_run_is_remembered_with_its_final_report(tmp_path):
    state = AgentState(tmp_path)
    state.mark_finished("r1", {"state": "done"})

    assert AgentState(tmp_path).finished("r1") == {"state": "done"}
    assert state.finished("r2") is None


def test_finished_runs_are_capped_oldest_first(tmp_path, monkeypatch):
    import agent_state

    monkeypatch.setattr(agent_state, "FINISHED_LIMIT", 2)
    state = AgentState(tmp_path)
    for run_id in ("r1", "r2", "r3"):
        state.mark_finished(run_id, {"state": "done"})

    assert state.finished("r1") is None
    assert state.finished("r3") == {"state": "done"}


def test_writes_leave_no_temporary_files(tmp_path):
    state = AgentState(tmp_path)
    state.enqueue("r1", {"step_index": 0})
    state.save_stations("m1", [])
    state.mark_finished("r1", {"state": "done"})

    assert not list(tmp_path.glob("*.tmp"))
    # And what is there is valid JSON.
    for path in tmp_path.glob("*.json"):
        json.loads(path.read_text())
