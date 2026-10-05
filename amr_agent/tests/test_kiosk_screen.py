"""Tests for kiosk/screen.py: which screen wins, and what the robot says."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kiosk"))

from screen import (  # noqa: E402
    ARRIVED,
    BLOCKED,
    CHARGING,
    ERROR,
    ESTOP,
    IDLE,
    LOWBAT,
    MOVING,
    OFFLINE,
    THANKS,
    Inputs,
    clock_text,
    countdown_text,
    screen_for,
    view_for,
)

ROUTE = ["Dapur", "Meja 5", "Meja 8", "Dapur"]


def live(**fields) -> Inputs:
    return Inputs(linked=True, **{"phase": "idle", **fields})


def test_phases_map_to_screens():
    assert screen_for(live()) == IDLE
    assert screen_for(live(phase="moving")) == MOVING
    assert screen_for(live(phase="near")) == MOVING
    assert screen_for(live(phase="blocked")) == BLOCKED
    assert screen_for(live(phase="waiting")) == ARRIVED
    assert screen_for(live(phase="thanks")) == THANKS
    assert screen_for(live(phase="failed")) == ERROR
    assert screen_for(live(phase="done")) == IDLE


def test_emergency_stop_beats_everything():
    assert screen_for(live(phase="waiting", estop=True)) == ESTOP
    assert screen_for(Inputs(estop=True)) == ESTOP


def test_an_order_waiting_beats_a_low_battery():
    # The person at the table still needs to take their order.
    assert screen_for(live(phase="waiting", battery=8)) == ARRIVED


def test_charging_and_low_battery_only_when_idle():
    assert screen_for(live(charging=True)) == CHARGING
    assert screen_for(live(battery=10)) == LOWBAT
    assert screen_for(live(phase="moving", battery=10)) == MOVING


def test_agent_not_heard_is_offline_not_idle():
    assert screen_for(Inputs()) == OFFLINE
    assert screen_for(Inputs(phase="idle", linked=False)) == OFFLINE
    assert screen_for(live(phase="off")) == OFFLINE
    # A robot on its charger with the agent still starting: say charging.
    assert screen_for(Inputs(charging=True)) == CHARGING


def test_moving_names_the_stop_and_nearly_there():
    view = view_for(live(phase="moving", route=ROUTE, step=1))
    assert view.title == "Menuju Meja 5"
    assert view.show_route
    near = view_for(live(phase="near", route=ROUTE, step=1))
    assert near.title == "Hampir sampai di Meja 5"
    assert near.mood == "eager"


def test_english():
    view = view_for(live(phase="moving", route=ROUTE, step=2, lang="en"))
    assert view.title == "Heading to Meja 8"
    assert view.pill == "Delivering"


def test_turn_intent_only_while_moving():
    assert view_for(live(phase="moving", route=ROUTE, step=1, intent="left")).intent_text == (
        "Saya belok kiri"
    )
    assert view_for(live(phase="blocked", intent="left")).intent_text == ""


def test_done_and_touch_reactions_on_idle():
    assert view_for(live(phase="done")).title == "Semua pesanan terantar"
    tickle = view_for(live(reaction="tickle"))
    assert tickle.title == "Hehe, geli!"
    assert tickle.mood == "happy"
    assert view_for(live(reaction="annoyed")).mood == "annoyed"
    # Not while delivering: the face is busy.
    assert view_for(live(phase="moving", route=ROUTE, step=1, reaction="tickle")).mood == "focused"


def test_error_carries_the_reason_for_staff():
    view = view_for(live(phase="failed", detail="navigation did not succeed (status 6)"))
    assert view.title == "Saya butuh bantuan"
    assert "status 6" in view.subtitle


def test_step_out_of_range_has_no_place():
    assert view_for(live(phase="moving", route=ROUTE, step=9)).place == ""


def test_countdown_words_and_clock():
    assert clock_text(120) == "2:00"
    assert clock_text(65) == "1:05"
    assert clock_text(None) == ""
    assert countdown_text("id", 120) == "Tidak ditekan? Robot lanjut sendiri"
    assert countdown_text("id", 30) == "Robot akan segera lanjut"
