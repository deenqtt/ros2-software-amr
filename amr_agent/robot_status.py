"""
One status for the whole system, in words everyone shares.

Until now a robot's condition was described four different ways:
master_control's robot_current_sts codes, the agent's own mode/state pair, the
backend's run states and the kiosk's phases. The dashboard, the robot page and
the kiosk each translated for themselves, and the translations disagreed —
master_control's code 2 means "waiting for the operator's OK", which the web
rendered as "Docking".

This module is the single translation. It takes the words the robot already
speaks and returns one of a small set of statuses the whole system shares:

  parked            navigation is not running (the registry's "idle").
  mapping           surveying; SLAM owns /map.
  ready             navigation up, no work, not on the charger.
  on_mission        executing a run.
  waiting_confirm   holding at a station for the operator's "OK".
  charging          on the charger.
  error             the last run failed and needs a person.
  paused            held by an operator; the mission is kept. Reserved — the
                    Pause control does not exist yet, the vocabulary does.

`offline` is deliberately not among them: a robot that cannot report is called
offline by the reader — the backend stamps status_reported_at, the web compares
age — never by the robot itself.

Priority is the point, and is tested: a failed run outranks everything (a robot
that just failed must not look busy), waiting for the operator outranks the
drive, and charging outranks "ready" but not the work of getting to the
charger. Where two words are true, this says which one a person needs.

No ROS imports, on purpose: like delivery.py and master_control_link.py, this
is the part that decides what people are told, and it is tested without a robot.
"""

from __future__ import annotations

from dataclasses import dataclass

STATUS_PARKED = "parked"
STATUS_MAPPING = "mapping"
STATUS_READY = "ready"
STATUS_ON_MISSION = "on_mission"
STATUS_WAITING_CONFIRM = "waiting_confirm"
STATUS_CHARGING = "charging"
STATUS_ERROR = "error"
STATUS_PAUSED = "paused"

#: The whole vocabulary, for validation on both ends of the report.
STATUSES = (
    STATUS_PARKED,
    STATUS_MAPPING,
    STATUS_READY,
    STATUS_ON_MISSION,
    STATUS_WAITING_CONFIRM,
    STATUS_CHARGING,
    STATUS_ERROR,
    STATUS_PAUSED,
)

# RobotStatus.robot_current_sts, as master_control fills it. Repeated here so
# the mapper stays importable on its own (master_control_link.STATUS_* agree).
MASTER_IDLE = 0
MASTER_MOVING = 1
MASTER_WAITING = 2

# Agent modes, as robot_agent_node.MODE_* spells them. Repeated for the same
# reason; the reporter maps nothing.
MODE_MAP = "map"
MODE_NAV = "nav"

#: Report even when nothing changed, so the reader can tell silence from
#: stillness: a status older than a few of these is treated as the robot
#: having gone quiet.
REPORT_INTERVAL_S = 15.0


@dataclass(frozen=True)
class Signals:
    """
    Everything the reporter knows at one instant.

    The fields mirror the four sources, unchanged: the agent's mode/state, what
    it knows of the current run, and master_control's last word. `None` means
    "no word" and is handled, never guessed at.
    """

    agent_mode: str = "unknown"
    agent_state: str = "idle"
    # The agent is executing (or about to execute) a run from the backend.
    run_active: bool = False
    # The most recent run ended in failure. Cleared when the next one starts.
    last_run_failed: bool = False
    last_run_detail: str = ""
    # Reserved for the Pause control.
    paused: bool = False
    # master_control's status code, or None once it has gone quiet.
    master_status: int | None = None
    waiting_for_operator: bool = False
    docked: bool | None = None
    charging: bool | None = None
    battery: float | None = None
    # What master_control last said it was doing, in web words.
    mission_detail: str = ""


@dataclass(frozen=True)
class Decision:
    """The status to report, and the one line that goes with it."""

    status: str
    detail: str = ""


def _battery_note(battery: float | None) -> str:
    if battery is None:
        return ""
    return f"battery {battery:.0f}%"


def unified_status(signals: Signals) -> Decision:
    """
    The one status this robot reports, from the words it already speaks.

    Ordered most-urgent-first. Each branch is a fact a person would act on;
    later branches are only reached when the earlier ones have nothing to say.
    """
    if signals.last_run_failed:
        return Decision(
            STATUS_ERROR, signals.last_run_detail or "the last mission failed"
        )
    if signals.paused:
        return Decision(
            STATUS_PAUSED, signals.mission_detail or "held by the operator"
        )
    # Both sources say the same thing two ways: master_control's code, and the
    # event stream's WAITING_VERIFICATION. Either one is a robot stopped at a
    # station with someone's order on it.
    if signals.waiting_for_operator or signals.master_status == MASTER_WAITING:
        return Decision(
            STATUS_WAITING_CONFIRM,
            signals.mission_detail or "waiting for the operator's OK",
        )
    if signals.run_active:
        return Decision(STATUS_ON_MISSION, signals.mission_detail or "driving a mission")
    if signals.agent_mode == MODE_MAP:
        return Decision(STATUS_MAPPING, "surveying the map")
    # Charging outranks parked and ready — a robot on the charger is not
    # available for work even when navigation is up.
    if signals.charging:
        return Decision(STATUS_CHARGING, _battery_note(signals.battery))
    if signals.agent_mode == MODE_NAV and signals.agent_state == "running":
        return Decision(STATUS_READY, _battery_note(signals.battery))
    # Navigation not up yet, switched off, or still starting.
    return Decision(STATUS_PARKED, "navigation is not running")
