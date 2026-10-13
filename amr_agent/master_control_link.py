"""
What the robot's master_control is doing, in the words the kiosk and web UI use.

On robots run with mission_via=mission_plan the agent hands each step to
master_control's /mission_plan action and master_control does the driving,
docking and waiting. It says what it is doing on two topics of its own, and
this module reads them so the agent can tell the screen on the robot and the
web UI, which only ever talk to the agent:

  /robot_status   custom_interfaces/RobotStatus, 1 Hz. robot_current_sts is
                  0 idle, 1 moving, 2 waiting for the operator's "OK".
  /amr_run_data   custom_interfaces/AmrRunData, one message per event:
                  STARTED, DOCK_STARTED, WAITING_VERIFICATION, UNDOCK_SUCCEEDED…

master_control is the reference here: its names and meanings are taken as they
are, and the agent adapts. Its operator confirm is /confirm_next_mission; the
agent forwards the kiosk's /mission_confirm to it.

No ROS imports, on purpose: this is the part that decides what a person
standing at the robot is told, and it is tested without a robot.
"""

from __future__ import annotations

import threading
import time

# RobotStatus.robot_current_sts, as master_control fills it.
STATUS_IDLE = 0
STATUS_MOVING = 1
STATUS_WAITING_VERIFICATION = 2

# master_control publishes /robot_status every second. Older than this and it
# is treated as unknown rather than trusted: a stale "waiting" would hold the
# kiosk on the OK button after master_control has gone.
STATUS_STALE_S = 3.5

# Phases on /amr/kiosk (see delivery.py). Repeated as strings so this module
# stays importable on its own.
PHASE_MOVING = "moving"
PHASE_BLOCKED = "blocked"
PHASE_WAITING = "waiting"

# AmrRunData.event_status → what the web UI's mission panel says, per step.
# `{station}` is the step's station name. Events not listed are shown as they
# come, lower-cased, so a new one master_control adds still says something.
EVENT_TEXT = {
    "STARTED": "driving to {station}",
    "RETRY_STARTED": "driving to {station} again",
    "IN_PROGRESS": "driving to {station}",
    "NAV_RETRYING": "could not reach {station}, retrying",
    "RETRYING_OBSTACLE": "blocked on the way to {station}, retrying",
    "SUCCEEDED": "arrived at {station}",
    "FAILED": "could not reach {station}",
    "CANCELED": "drive to {station} canceled",
    "WAITING_VERIFICATION": "waiting for the operator at {station}",
    "VERIFIED": "confirmed at {station}",
    "DOCK_STARTED": "docking at {station}",
    "DOCK_RETRY_STARTED": "docking at {station} again",
    "DOCK_RETRYING": "docking at {station} failed, retrying",
    "DOCK_SUCCEEDED": "docked at {station}",
    "DOCK_FAILED": "could not dock at {station}",
    "UNDOCK_STARTED": "undocking from {station}",
    "UNDOCK_RETRY_STARTED": "undocking from {station} again",
    "UNDOCK_RETRYING": "undocking from {station} failed, retrying",
    "UNDOCK_SUCCEEDED": "left {station}",
    "UNDOCK_SKIPPED": "left {station}",
    "LOW_BATTERY_DOCK_STARTED": "battery low, going to charge",
}

# Events after which the robot is not getting anywhere for the moment: the
# kiosk shows its "excuse me" face rather than "on my way".
BLOCKED_EVENTS = frozenset(
    {"NAV_RETRYING", "RETRYING_OBSTACLE", "DOCK_RETRYING", "UNDOCK_RETRYING"}
)


def event_detail(event: str, station: str) -> str:
    """The web UI's line for one master_control event at one station."""
    event = str(event or "").strip().upper()
    if not event:
        return ""
    template = EVENT_TEXT.get(event)
    if template is None:
        return event.lower().replace("_", " ")
    return template.format(station=station or "the station")


def rejection_detail(battery: float | None, minimum: float) -> str:
    """
    Why master_control refused a step, as far as the agent can tell.

    master_control refuses a mission goal only for a low battery, and says so
    in its own log alone. The agent sees the battery on /robot_status and can
    name the likely cause instead of a bare "rejected".
    """
    if battery is not None and battery <= minimum:
        return (
            f"master_control refused the step: battery {battery:.0f}% is at or "
            f"below the {minimum:.0f}% it needs to start a mission"
        )
    return "master_control refused the step"


class MasterControlLink:
    """
    The latest word from master_control, safe to read from any thread.

    Fed by the agent's subscriptions; read by the step that is running.
    """

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._status: int | None = None
        self._status_at: float | None = None
        self._battery: float | None = None
        self._docked: bool | None = None
        self._event: str = ""
        self._event_index: int | None = None
        self._feedback: str = ""

    # ── Inputs ────────────────────────────────────────────────────────────────

    def on_status(self, status: int, battery: float | None, docked: bool) -> None:
        with self._lock:
            self._status = int(status)
            self._status_at = self._clock()
            self._battery = None if battery is None else float(battery)
            self._docked = bool(docked)

    def on_event(self, event: str, index: int | None = None) -> None:
        with self._lock:
            # Delivered reliably but possibly twice after a reconnect; the
            # index tells a repeat from a new event of the same name.
            if index is not None and index == self._event_index:
                return
            self._event = str(event or "").strip().upper()
            self._event_index = index

    def on_feedback(self, mission_sts: str) -> None:
        """MissionPlan feedback, for when master_control starts sending it."""
        with self._lock:
            self._feedback = str(mission_sts or "").strip().upper()

    def begin_step(self) -> None:
        """Forget the last step's event and feedback: they are not this step's."""
        with self._lock:
            self._event = ""
            self._event_index = None
            self._feedback = ""

    # ── Reading ───────────────────────────────────────────────────────────────

    @property
    def battery(self) -> float | None:
        with self._lock:
            return self._battery

    def status(self) -> int | None:
        """robot_current_sts, or None when master_control has gone quiet."""
        with self._lock:
            if self._status_at is None or self._clock() - self._status_at > STATUS_STALE_S:
                return None
            return self._status

    def waiting_for_operator(self) -> bool:
        """master_control is holding at a station for its "OK"."""
        if self.status() == STATUS_WAITING_VERIFICATION:
            return True
        with self._lock:
            return self._feedback in ("WAITING_OPERATOR", "WAITING_PAYLOAD")

    def phase(self) -> str:
        """The kiosk phase for the step in progress."""
        if self.waiting_for_operator():
            return PHASE_WAITING
        with self._lock:
            event = self._event
        if event in BLOCKED_EVENTS:
            return PHASE_BLOCKED
        return PHASE_MOVING

    def detail(self, station: str) -> str:
        """The web UI's line for the step in progress, or "" before any word."""
        with self._lock:
            event = self._event
            feedback = self._feedback
        if self.waiting_for_operator():
            return event_detail("WAITING_VERIFICATION", station)
        if event:
            return event_detail(event, station)
        if feedback:
            return feedback.lower().replace("_", " ")
        return ""
