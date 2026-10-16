"""
The unified status mapper, decided from the words the robot already speaks.

The priority order is the contract: a failed run must never look busy, waiting
for the operator must never look like driving, and charging must never look
like readiness. Each test below pins one such "two words are true, this one
wins" case, plus the honest defaults when a source says nothing.
"""

from robot_status import (
    REPORT_INTERVAL_S,
    STATUS_CHARGING,
    STATUS_ERROR,
    STATUS_MAPPING,
    STATUS_ON_MISSION,
    STATUS_PAUSED,
    STATUS_PARKED,
    STATUS_READY,
    STATUS_WAITING_CONFIRM,
    STATUSES,
    Signals,
    unified_status,
)


def test_every_status_is_reachable_or_reserved():
    # paused has no control yet; the word exists so the vocabulary does not
    # change shape when the control arrives.
    assert set(STATUSES) == {
        STATUS_PARKED,
        STATUS_MAPPING,
        STATUS_READY,
        STATUS_ON_MISSION,
        STATUS_WAITING_CONFIRM,
        STATUS_CHARGING,
        STATUS_ERROR,
        STATUS_PAUSED,
    }


def test_nothing_said_yet_is_parked():
    assert unified_status(Signals()).status == STATUS_PARKED


def test_navigation_running_is_ready():
    decision = unified_status(Signals(agent_mode="nav", agent_state="running", battery=87.0))
    assert decision.status == STATUS_READY
    assert decision.detail == "battery 87%"


def test_surveying_is_mapping():
    assert unified_status(Signals(agent_mode="map", agent_state="running")).status == STATUS_MAPPING


def test_a_failed_run_is_error_and_names_what_failed():
    decision = unified_status(
        Signals(
            agent_mode="nav",
            agent_state="running",
            last_run_failed=True,
            last_run_detail="lap 1, step 2: no valid path found",
        )
    )
    assert decision.status == STATUS_ERROR
    assert decision.detail == "lap 1, step 2: no valid path found"


def test_a_failure_without_words_says_so():
    decision = unified_status(Signals(last_run_failed=True))
    assert decision.status == STATUS_ERROR
    assert decision.detail == "the last mission failed"


def test_error_outranks_a_running_mission():
    # The run thread may still be winding down when the failure lands; the
    # robot must not read as busy to someone deciding whether to intervene.
    decision = unified_status(Signals(run_active=True, last_run_failed=True))
    assert decision.status == STATUS_ERROR


def test_waiting_for_the_operator_outranks_the_drive():
    decision = unified_status(
        Signals(
            run_active=True,
            master_status=2,
            mission_detail="waiting for the operator at Table 3",
        )
    )
    assert decision.status == STATUS_WAITING_CONFIRM
    assert decision.detail == "waiting for the operator at Table 3"


def test_master_controls_code_two_means_waiting_even_without_a_run():
    # An agent that restarted mid-mission has no run thread yet, but
    # master_control is still holding at a station.
    assert unified_status(Signals(master_status=2)).status == STATUS_WAITING_CONFIRM


def test_a_running_mission_is_on_mission_with_master_controls_words():
    decision = unified_status(
        Signals(run_active=True, master_status=1, mission_detail="docking at Table 3")
    )
    assert decision.status == STATUS_ON_MISSION
    assert decision.detail == "docking at Table 3"


def test_a_mission_without_master_control_still_says_on_mission():
    # master_control gone quiet (status None) is not "not busy".
    decision = unified_status(Signals(run_active=True))
    assert decision.status == STATUS_ON_MISSION
    assert decision.detail == "driving a mission"


def test_on_the_charger_is_charging_even_when_navigation_is_up():
    decision = unified_status(
        Signals(agent_mode="nav", agent_state="running", charging=True, battery=44.0)
    )
    assert decision.status == STATUS_CHARGING
    assert decision.detail == "battery 44%"


def test_charging_does_not_hide_a_mission():
    # The drive to the charger is work; a robot backing onto the charger is
    # on_mission until it is actually on one.
    assert unified_status(Signals(run_active=True, charging=True)).status == STATUS_ON_MISSION


def test_paused_says_what_it_is_holding():
    assert unified_status(Signals(paused=True, mission_detail="at Table 3")).detail == "at Table 3"


def test_parked_when_navigation_is_not_running():
    assert unified_status(Signals(agent_mode="stop")).status == STATUS_PARKED
    assert unified_status(Signals(agent_mode="nav", agent_state="idle")).status == STATUS_PARKED


def test_master_control_silent_is_not_parked():
    # In a plain-Nav2 setup master_control never speaks; navigation up is
    # still ready.
    decision = unified_status(Signals(agent_mode="nav", agent_state="running", master_status=None))
    assert decision.status == STATUS_READY


def test_report_interval_leaves_room_for_a_missed_beat():
    # The reader treats a status as stale a few intervals after the last
    # report; the interval itself is small enough that silence is noticed
    # within a minute.
    assert 5 <= REPORT_INTERVAL_S <= 30
