"""AgentState: the registry snapshot, and the last known pose per map."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_state import AgentState, pose_changed  # noqa: E402


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


# ── Last known pose ─────────────────────────────────────────────────────────

def test_a_pose_is_kept_per_map(tmp_path):
    state = AgentState(tmp_path)
    state.save_pose("m1", 1.5, -2.0, 0.75)
    state.save_pose("m2", 9.0, 9.0, -3.0)
    assert state.load_pose("m1") == (1.5, -2.0, 0.75)
    assert state.load_pose("m2") == (9.0, 9.0, -3.0)
    assert state.load_pose("m3") is None


def test_a_pose_survives_a_restart(tmp_path):
    AgentState(tmp_path).save_pose("m1", 1.0, 2.0, 3.0)
    assert AgentState(tmp_path).load_pose("m1") == (1.0, 2.0, 3.0)


def test_a_later_pose_replaces_the_earlier_one(tmp_path):
    state = AgentState(tmp_path)
    state.save_pose("m1", 1.0, 2.0, 0.0)
    state.save_pose("m1", 4.0, 5.0, 0.5)
    assert state.load_pose("m1") == (4.0, 5.0, 0.5)


def test_a_non_finite_pose_is_refused(tmp_path):
    state = AgentState(tmp_path)
    with pytest.raises(ValueError):
        state.save_pose("m1", math.nan, 0.0, 0.0)
    assert state.load_pose("m1") is None


@pytest.mark.parametrize(
    "content",
    ["not json", "[]", '{"x": 1, "y": 2}', '{"x": "a", "y": 2, "yaw": 0}',
     '{"x": NaN, "y": 2, "yaw": 0}'],
)
def test_a_damaged_pose_file_reads_as_none(tmp_path, content):
    state = AgentState(tmp_path)
    (tmp_path / "pose_m1.json").write_text(content)
    assert state.load_pose("m1") is None


def test_pose_changed():
    old = (1.0, 1.0, 0.0)
    assert pose_changed(None, old)
    assert not pose_changed(old, (1.01, 1.01, 0.01))
    assert pose_changed(old, (1.1, 1.0, 0.0))
    assert pose_changed(old, (1.0, 1.0, 0.2))
    # Across the +pi / -pi seam is a tiny turn, not a full one.
    assert not pose_changed((0.0, 0.0, math.pi - 0.01), (0.0, 0.0, -math.pi + 0.01))
