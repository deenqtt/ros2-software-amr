"""Tests for delivery.py: no ROS, no robot, a fake clock."""

import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from delivery import (  # noqa: E402
    CONFIRMED,
    PHASE_BLOCKED,
    PHASE_MOVING,
    PHASE_NEAR,
    STOPPED,
    TIMED_OUT,
    ConfirmGate,
    ProgressWatch,
    kiosk_status,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# ── ProgressWatch ────────────────────────────────────────────────────────────


def test_driving_closer_is_moving_then_near():
    clock = Clock()
    watch = ProgressWatch(clock)
    assert watch.update(8.0) == PHASE_MOVING
    clock.now += 3
    assert watch.update(5.0) == PHASE_MOVING
    clock.now += 3
    assert watch.update(1.2) == PHASE_NEAR


def test_no_path_yet_is_not_arrived():
    watch = ProgressWatch(Clock())
    assert watch.update(0.0) == PHASE_MOVING


def test_no_progress_for_a_while_is_blocked_and_recovers():
    clock = Clock()
    watch = ProgressWatch(clock)
    watch.update(6.0)
    clock.now += 9
    assert watch.update(5.95) == PHASE_BLOCKED
    clock.now += 1
    assert watch.update(5.0) == PHASE_MOVING


def test_turning_on_the_spot_at_the_goal_is_not_blocked():
    clock = Clock()
    watch = ProgressWatch(clock)
    watch.update(1.0)
    clock.now += 20
    assert watch.update(0.95) == PHASE_NEAR


def test_a_recovery_shows_blocked_for_a_moment():
    clock = Clock()
    watch = ProgressWatch(clock)
    watch.update(6.0, recoveries=0)
    clock.now += 1
    assert watch.update(5.5, recoveries=1) == PHASE_BLOCKED
    clock.now += 2
    assert watch.update(5.0, recoveries=1) == PHASE_BLOCKED
    clock.now += 4
    assert watch.update(4.5, recoveries=1) == PHASE_MOVING


def test_reset_forgets_the_previous_goal():
    clock = Clock()
    watch = ProgressWatch(clock)
    watch.update(0.5, recoveries=3)
    watch.reset()
    clock.now += 1
    assert watch.update(7.0, recoveries=0) == PHASE_MOVING


# ── ConfirmGate ──────────────────────────────────────────────────────────────


def test_confirm_answers_an_open_gate():
    gate = ConfirmGate()
    gate.open(120)
    threading.Timer(0.05, gate.confirm).start()
    assert gate.wait(poll_s=0.01) == CONFIRMED
    assert not gate.is_open


def test_confirm_with_nothing_waiting_is_refused_and_not_remembered():
    gate = ConfirmGate()
    assert gate.confirm() is False
    gate.open(0.05)
    # The earlier tap must not answer this stop.
    assert gate.wait(poll_s=0.01) == TIMED_OUT


def test_timeout_carries_on():
    clock = Clock()
    gate = ConfirmGate(clock)
    gate.open(120)
    assert gate.remaining() == 120
    clock.now += 119.5
    assert gate.remaining() == pytest.approx(0.5)
    clock.now += 1
    assert gate.wait(poll_s=0.001) == TIMED_OUT
    assert gate.remaining() is None


def test_stop_ends_the_wait():
    gate = ConfirmGate()
    gate.open(120)
    assert gate.wait(should_stop=lambda: True, poll_s=0.001) == STOPPED
    assert gate.confirm() is False


def test_zero_timeout_waits_until_answered():
    clock = Clock()
    gate = ConfirmGate(clock)
    gate.open(0)
    assert gate.remaining() is None
    assert gate.timeout is None
    clock.now += 10_000
    threading.Timer(0.05, gate.confirm).start()
    assert gate.wait(poll_s=0.01) == CONFIRMED


# ── kiosk_status ─────────────────────────────────────────────────────────────


def test_status_rounds_remaining_up():
    status = kiosk_status(
        phase="waiting",
        route=["Dapur", "Meja 5"],
        step=1,
        confirm_remaining=0.2,
        confirm_timeout=120.0,
    )
    assert status["confirm_remaining"] == 1
    assert status["confirm_timeout"] == 120
    assert status["route"] == ["Dapur", "Meja 5"]
    assert kiosk_status(phase="waiting", confirm_remaining=30.0)["confirm_remaining"] == 30


def test_status_refuses_an_unknown_phase():
    with pytest.raises(ValueError):
        kiosk_status(phase="dancing")
