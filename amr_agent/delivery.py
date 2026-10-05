"""
What a delivery looks like from outside the robot, for the screen on it.

Nav2 reports a drive as a distance and a count of recoveries; the person
standing by the table wants to know "is it nearly here", "is it stuck", "may I
take my order". This module turns the first into the second, and holds a
`confirm` step open until somebody answers or the time runs out.

No ROS imports, on purpose: it is the part of the kiosk work that has to be
right, and it is tested without a robot (tests/test_delivery.py).
"""

from __future__ import annotations

import threading
import time

# Phases on /amr/kiosk. The screen picks its face and words from these.
PHASE_IDLE = "idle"  # navigating, no run
PHASE_MOVING = "moving"
PHASE_NEAR = "near"  # the last stretch to a stop
PHASE_BLOCKED = "blocked"  # recovering, or not getting any closer
PHASE_WAITING = "waiting"  # at a `confirm` stop, waiting for the order to be taken
PHASE_THANKS = "thanks"  # just confirmed; a moment before driving on
PHASE_DONE = "done"  # the run finished
PHASE_FAILED = "failed"  # the run stopped on an error; somebody has to come
PHASE_OFF = "off"  # not navigating at all (mapping, stopped, starting)

PHASES = (
    PHASE_IDLE,
    PHASE_MOVING,
    PHASE_NEAR,
    PHASE_BLOCKED,
    PHASE_WAITING,
    PHASE_THANKS,
    PHASE_DONE,
    PHASE_FAILED,
    PHASE_OFF,
)

# Within this of the goal, the robot is "nearly there". Far enough out that the
# screen says so a few seconds before arrival at walking pace.
NEAR_DISTANCE_M = 1.5
# No closer by this much over STALL_S, and the robot is treated as blocked.
# Nav2 rotating on the spot or waiting out a person in the corridor makes no
# progress either, and that is exactly what "Permisi" is for.
STALL_PROGRESS_M = 0.2
STALL_S = 8.0
# A recovery (clearing costmaps, backing up, spinning) shows as blocked for at
# least this long, so one quick recovery does not flicker the face.
RECOVERY_HOLD_S = 5.0

CONFIRMED = "confirmed"
TIMED_OUT = "timeout"
STOPPED = "stopped"


class ProgressWatch:
    """
    Reads Nav2's navigate_to_pose feedback for one goal.

    `update` takes the two fields that matter and returns the phase to show.
    Reset between goals: the distance of the previous stop says nothing about
    this one.
    """

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self.reset()

    def reset(self) -> None:
        self._best: float | None = None
        self._progress_at = self._clock()
        self._recoveries = 0
        self._recovery_at: float | None = None
        self.phase = PHASE_MOVING

    def update(self, distance_remaining: float, recoveries: int = 0) -> str:
        now = self._clock()
        # Nav2 reports 0 until it has a path. Unknown, not arrived.
        known = distance_remaining > 0.0
        if known and (self._best is None or distance_remaining < self._best - STALL_PROGRESS_M):
            self._best = distance_remaining
            self._progress_at = now
        if recoveries > self._recoveries:
            self._recoveries = recoveries
            self._recovery_at = now

        if self._recovery_at is not None and now - self._recovery_at < RECOVERY_HOLD_S:
            self.phase = PHASE_BLOCKED
        elif known and distance_remaining <= NEAR_DISTANCE_M:
            # Close in, a robot turning to its final heading makes no progress
            # and is not stuck.
            self.phase = PHASE_NEAR
        elif now - self._progress_at > STALL_S:
            self.phase = PHASE_BLOCKED
        else:
            self.phase = PHASE_MOVING
        return self.phase


class ConfirmGate:
    """
    One arrival waiting for somebody to say the order was taken.

    `confirm` only counts while the gate is open: a second tap on the screen,
    or a confirm sent while the robot is still driving, must not answer the
    *next* stop before anybody is standing at it.
    """

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._open = False
        self._deadline: float | None = None
        self._timeout: float | None = None

    def open(self, timeout_s: float) -> None:
        """Start waiting. A timeout of 0 or less waits until answered."""
        with self._lock:
            self._event.clear()
            self._open = True
            self._timeout = timeout_s if timeout_s > 0 else None
            self._deadline = self._clock() + timeout_s if timeout_s > 0 else None

    def confirm(self) -> bool:
        """True when this answered a waiting stop."""
        with self._lock:
            if not self._open:
                return False
            self._event.set()
            return True

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._open

    @property
    def timeout(self) -> float | None:
        with self._lock:
            return self._timeout if self._open else None

    def remaining(self) -> float | None:
        """Seconds left, or None when not waiting or waiting without a limit."""
        with self._lock:
            if not self._open or self._deadline is None:
                return None
            return max(0.0, self._deadline - self._clock())

    def wait(self, should_stop=lambda: False, poll_s: float = 0.2) -> str:
        """
        Block until confirmed, timed out, or `should_stop()` says to give up.

        `should_stop` is checked every poll, so the run being canceled from the
        web UI or the robot leaving navigation ends the wait promptly.
        """
        try:
            while True:
                if self._event.wait(poll_s):
                    return CONFIRMED
                if should_stop():
                    return STOPPED
                with self._lock:
                    deadline = self._deadline
                if deadline is not None and self._clock() >= deadline:
                    # One last look: a confirm in the final poll still counts.
                    return CONFIRMED if self._event.is_set() else TIMED_OUT
        finally:
            with self._lock:
                self._open = False
                self._deadline = None


def kiosk_status(
    *,
    phase: str,
    robot_mode: str = "",
    mission: str = "",
    route: list[str] | None = None,
    step: int | None = None,
    lap: int | None = None,
    laps: int | None = None,
    confirm_remaining: float | None = None,
    confirm_timeout: float | None = None,
    detail: str = "",
) -> dict:
    """
    The message on /amr/kiosk.

    Station *names*, not ids: the screen shows them to guests and has no
    registry to look ids up in. Remaining time is whole seconds, rounded up, so
    the screen never shows 0 while the robot is still waiting.
    """
    if phase not in PHASES:
        raise ValueError(f"unknown kiosk phase {phase!r}")
    remaining = None
    if confirm_remaining is not None:
        whole = int(confirm_remaining)
        remaining = whole if whole == confirm_remaining else whole + 1
    return {
        "v": 1,
        "phase": phase,
        "robot_mode": robot_mode,
        "mission": mission,
        "route": list(route or []),
        "step": step,
        "lap": lap,
        "laps": laps,
        "confirm_remaining": remaining,
        "confirm_timeout": int(confirm_timeout) if confirm_timeout else None,
        "detail": detail,
    }
