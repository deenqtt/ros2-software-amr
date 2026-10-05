"""
Where the kiosk's facts come from.

RosSource reads the robot: /amr/kiosk from the agent, /battery_state, and an
optional emergency-stop topic. MockSource plays a delivery by itself, for
working on the screen at a desk with no ROS installed (--mock).

Both report through `push(fields)`, a dict of Inputs fields, and both may be
told `confirm()`. The controller never knows which one it has.
"""

from __future__ import annotations

import json
import math
import threading
import time

from PySide6.QtCore import QObject, QTimer

MOCK_ROUTE = ["Dapur", "Meja 5", "Meja 8", "Dapur"]
MOCK_CONFIRM_AT = {1, 2}  # stops that wait for "Sudah diambil"
MOCK_DRIVE_S = 7.0
MOCK_TIMEOUT_S = 120


class MockSource(QObject):
    """
    A delivery, faked. Keys (from the window):
      1 idle   2 deliver   3 blocked   4 arrived   5 thanks   6 charging
      7 low battery   8 error   9 emergency stop   + / - battery
    """

    def __init__(self, push, parent=None) -> None:
        super().__init__(parent)
        self._push = push
        self._phase = "idle"
        self._step = 0
        self._entered = time.monotonic()
        self._deadline: float | None = None
        self._battery = 82.0
        self._charging = False
        self._estop = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(200)
        self._emit()

    # ── Controls ─────────────────────────────────────────────────────────────

    def key(self, key: str) -> None:
        self._estop = False if key != "9" else not self._estop
        if key == "1":
            self._charging = False
            self._set("idle")
        elif key == "2":
            self._charging = False
            self._step = 1
            self._set("moving")
        elif key == "3":
            self._step = max(1, self._step)
            self._set("blocked")
        elif key == "4":
            self._step = 1 if self._step not in MOCK_CONFIRM_AT else self._step
            self._arrive()
        elif key == "5":
            self._step = max(1, self._step)
            self._set("thanks")
        elif key == "6":
            self._charging = True
            self._set("idle")
        elif key == "7":
            self._charging = False
            self._battery = 12.0
            self._set("idle")
        elif key == "8":
            self._step = max(1, self._step)
            self._set("failed")
        elif key in ("+", "="):
            self._battery = min(100.0, self._battery + 10)
        elif key == "-":
            self._battery = max(0.0, self._battery - 10)
        self._emit()

    def confirm(self) -> bool:
        if self._phase != "waiting":
            return False
        self._set("thanks")
        self._emit()
        return True

    # ── Simulation ───────────────────────────────────────────────────────────

    def _set(self, phase: str) -> None:
        self._phase = phase
        self._entered = time.monotonic()
        self._deadline = None

    def _arrive(self) -> None:
        if self._step in MOCK_CONFIRM_AT:
            self._set("waiting")
            self._deadline = time.monotonic() + MOCK_TIMEOUT_S
        else:
            self._next()

    def _next(self) -> None:
        if self._step >= len(MOCK_ROUTE) - 1:
            self._step = 0
            self._set("done")
        else:
            self._step += 1
            self._set("moving")

    def _tick(self) -> None:
        elapsed = time.monotonic() - self._entered
        if self._charging:
            self._battery = min(100.0, self._battery + 0.1)
        if self._phase in ("moving", "near"):
            if elapsed >= MOCK_DRIVE_S:
                self._arrive()
            elif elapsed >= MOCK_DRIVE_S - 2.2:
                self._phase = "near"
        elif self._phase == "waiting" and self._deadline and time.monotonic() >= self._deadline:
            self._next()
        elif self._phase == "thanks" and elapsed >= 3.0:
            self._next()
        elif self._phase == "done" and elapsed >= 10.0:
            self._set("idle")
        self._emit()

    def _emit(self) -> None:
        elapsed = time.monotonic() - self._entered
        moving = self._phase in ("moving", "near")
        intent = ""
        if moving and 1.5 <= elapsed < 3.6:
            intent = "left" if self._step % 2 else "right"
        remaining = None
        if self._phase == "waiting" and self._deadline:
            remaining = max(0, math.ceil(self._deadline - time.monotonic()))
        busy = self._phase not in ("idle", "done")
        self._push(
            {
                "phase": self._phase,
                "linked": True,
                "route": MOCK_ROUTE if busy else [],
                "step": self._step if busy else None,
                "confirm_remaining": remaining,
                "confirm_timeout": MOCK_TIMEOUT_S if remaining is not None else None,
                "detail": "lap 1, step 2: navigation did not succeed (status 6)"
                if self._phase == "failed"
                else "",
                "battery": self._battery,
                "charging": self._charging,
                "estop": self._estop,
                "intent": intent,
                "mission": "Antar makan siang" if busy else "",
                "robot_mode": "nav/running",
            }
        )


class RosSource:
    """
    The robot's own topics, read on a background thread.

    Local only: the kiosk runs on the robot, next to the agent, so it keeps
    working when wifi or the server drops — which is when a guest most needs
    to be told what is going on.
    """

    KIOSK_TOPIC = "/amr/kiosk"
    BATTERY_TOPIC = "/battery_state"
    CONFIRM_SERVICE = "/mission_confirm"
    # The agent publishes every second. Three missed and it is gone.
    LINK_TIMEOUT_S = 3.5

    def __init__(self, push, estop_topic: str = "") -> None:
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
        from sensor_msgs.msg import BatteryState
        from std_msgs.msg import Bool, String
        from std_srvs.srv import Trigger

        self._push = push
        self._rclpy = rclpy
        self._trigger = Trigger
        self._heard = 0.0
        rclpy.init()
        self._node = Node("amr_kiosk")
        latched = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self._node.create_subscription(String, self.KIOSK_TOPIC, self._on_kiosk, latched)
        self._node.create_subscription(BatteryState, self.BATTERY_TOPIC, self._on_battery, 10)
        if estop_topic:
            self._node.create_subscription(
                Bool, estop_topic, lambda msg: self._push({"estop": bool(msg.data)}), 10
            )
        self._confirm = self._node.create_client(Trigger, self.CONFIRM_SERVICE)
        self._node.create_timer(1.0, self._watch_link)
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self) -> None:
        try:
            self._executor.spin()
        except Exception:  # noqa: BLE001 — shutdown raises from inside spin
            pass

    def _on_kiosk(self, msg) -> None:
        try:
            data = json.loads(msg.data)
        except ValueError:
            return
        self._heard = time.monotonic()
        self._push(
            {
                "linked": True,
                "phase": str(data.get("phase") or ""),
                "route": [str(name) for name in data.get("route") or []],
                "step": data.get("step"),
                "confirm_remaining": data.get("confirm_remaining"),
                "confirm_timeout": data.get("confirm_timeout"),
                "detail": str(data.get("detail") or ""),
                "mission": str(data.get("mission") or ""),
                "robot_mode": str(data.get("robot_mode") or ""),
                "intent": str(data.get("intent") or ""),
            }
        )

    def _on_battery(self, msg) -> None:
        fields = {"charging": msg.power_supply_status == 1}  # POWER_SUPPLY_STATUS_CHARGING
        percentage = float(msg.percentage)
        if not math.isnan(percentage):
            # The message says 0..1; some drivers publish 0..100 anyway.
            fields["battery"] = percentage * 100.0 if percentage <= 1.0 else percentage
        self._push(fields)

    def _watch_link(self) -> None:
        if self._heard and time.monotonic() - self._heard > self.LINK_TIMEOUT_S:
            self._push({"linked": False})

    def confirm(self) -> bool:
        """Ask the agent to drive on. Answered asynchronously; the topic shows the result."""
        if not self._confirm.service_is_ready():
            return False
        self._confirm.call_async(self._trigger.Request())
        return True

    def key(self, key: str) -> None:
        del key  # the real robot is not driven from the keyboard

    def close(self) -> None:
        try:
            self._executor.shutdown()
            self._node.destroy_node()
            self._rclpy.try_shutdown()
        except Exception:  # noqa: BLE001
            pass
