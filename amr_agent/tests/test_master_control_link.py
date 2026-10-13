"""master_control_link: what master_control says, as the kiosk and web UI say it."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from master_control_link import (  # noqa: E402
    PHASE_BLOCKED,
    PHASE_MOVING,
    PHASE_WAITING,
    STATUS_IDLE,
    STATUS_MOVING,
    STATUS_STALE_S,
    STATUS_WAITING_VERIFICATION,
    MasterControlLink,
    event_detail,
    rejection_detail,
)


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def link_at(clock=None):
    return MasterControlLink(clock=clock or Clock())


# ── Events in words ─────────────────────────────────────────────────────────


def test_known_events_name_the_station():
    assert event_detail("DOCK_STARTED", "Dock A") == "docking at Dock A"
    assert event_detail("WAITING_VERIFICATION", "Meja 5") == "waiting for the operator at Meja 5"
    assert event_detail("UNDOCK_SKIPPED", "Dock A") == "left Dock A"


def test_an_unknown_event_still_says_something():
    assert event_detail("LIFT_RAISED", "Dock A") == "lift raised"
    assert event_detail("", "Dock A") == ""


def test_an_unnamed_station_is_still_a_sentence():
    assert event_detail("DOCK_STARTED", "") == "docking at the station"


# ── Waiting for the operator ────────────────────────────────────────────────


def test_status_two_is_waiting_for_the_operator():
    link = link_at()
    link.on_status(STATUS_WAITING_VERIFICATION, 80.0, True)
    assert link.waiting_for_operator()
    assert link.phase() == PHASE_WAITING
    assert link.detail("Dock A") == "waiting for the operator at Dock A"


def test_moving_and_idle_are_not_waiting():
    link = link_at()
    for status in (STATUS_IDLE, STATUS_MOVING):
        link.on_status(status, 80.0, False)
        assert not link.waiting_for_operator()


def test_a_stale_status_is_not_trusted():
    # master_control gone quiet must not leave the kiosk holding an OK button.
    clock = Clock()
    link = link_at(clock)
    link.on_status(STATUS_WAITING_VERIFICATION, 80.0, True)
    clock.now += STATUS_STALE_S + 0.1
    assert link.status() is None
    assert not link.waiting_for_operator()


def test_mission_feedback_can_say_waiting_too():
    # For when master_control starts sending MissionPlan feedback.
    link = link_at()
    link.on_feedback("WAITING_PAYLOAD")
    assert link.waiting_for_operator()


# ── Phase for the kiosk ─────────────────────────────────────────────────────


def test_retries_show_as_blocked():
    link = link_at()
    link.on_status(STATUS_MOVING, 80.0, False)
    link.on_event("DOCK_RETRYING", 7)
    assert link.phase() == PHASE_BLOCKED
    link.on_event("DOCK_RETRY_STARTED", 8)
    assert link.phase() == PHASE_MOVING


def test_detail_follows_the_latest_event():
    link = link_at()
    link.on_status(STATUS_MOVING, 80.0, False)
    link.on_event("STARTED", 1)
    assert link.detail("Dock A") == "driving to Dock A"
    link.on_event("DOCK_STARTED", 2)
    assert link.detail("Dock A") == "docking at Dock A"


def test_a_repeated_event_index_is_ignored():
    link = link_at()
    link.on_event("DOCK_STARTED", 4)
    link.on_event("DOCK_FAILED", 4)
    assert link.detail("Dock A") == "docking at Dock A"


def test_a_new_step_forgets_the_last_steps_event():
    link = link_at()
    link.on_event("UNDOCK_SUCCEEDED", 9)
    link.begin_step()
    assert link.detail("Dock B") == ""
    assert link.phase() == PHASE_MOVING


# ── Refused steps ───────────────────────────────────────────────────────────


def test_a_refusal_on_low_battery_says_so():
    text = rejection_detail(25.0, 30.0)
    assert "25%" in text and "30%" in text


def test_a_refusal_without_a_known_cause_says_only_that():
    assert rejection_detail(None, 30.0) == "master_control refused the step"
    assert rejection_detail(80.0, 30.0) == "master_control refused the step"


def test_battery_comes_from_the_status():
    link = link_at()
    assert link.battery is None
    link.on_status(STATUS_IDLE, 42.5, False)
    assert link.battery == 42.5
