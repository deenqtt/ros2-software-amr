"""AgentState registry snapshot: a robot with no map assigned yet."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_state import AgentState  # noqa: E402


def test_saving_twice_without_a_map_does_not_crash(tmp_path):
    # A freshly registered robot has no map: the first sync stores
    # map_record=null, and the next one used to crash reading it back.
    state = AgentState(tmp_path)
    state.save_registry(active_map_id=None, desired_mode="nav")
    state.save_registry(active_map_id=None, desired_mode="nav")
    assert state.load_registry()["map_record"] is None


def test_a_reread_assignment_keeps_the_map_it_had(tmp_path):
    state = AgentState(tmp_path)
    record = {"id": "m1", "content_hash": "abc"}
    state.save_registry(active_map_id="m1", desired_mode="nav", map_record=record)
    state.save_registry(active_map_id="m1", desired_mode="nav")
    assert state.load_registry()["map_record"] == record


def test_a_new_map_after_none_is_stored(tmp_path):
    state = AgentState(tmp_path)
    state.save_registry(active_map_id=None, desired_mode="nav")
    record = {"id": "m2"}
    state.save_registry(active_map_id="m2", desired_mode="nav", map_record=record)
    assert state.load_registry()["map_record"] == record
