#!/usr/bin/env python3
"""
A stand-in for the robot team's master_control, for trying mission_plan in sim.

master_control's /mission_plan executor is not written yet. This plays the part
it is expected to play, using master_control's own names, so the agent, the
kiosk and the web UI can be tried end to end with mission_via=mission_plan:

  action   /mission_plan          custom_interfaces/action/MissionPlan
  topic    /robot_status          custom_interfaces/msg/RobotStatus (1 Hz)
  topic    /amr_run_data          custom_interfaces/msg/AmrRunData (per event)
  service  /confirm_next_mission  std_srvs/Trigger (operator "OK")

For one goal: drive to the station with Nav2, pretend to dock (pick/drop
steps), wait for the operator when continue_mode is false, pretend to undock,
report "SUCCESS: <station>". Docking, undocking and the payload are timed
pretences, not motion: the real master_control does those.

Stations come from the dock database the agent writes (its station_file,
--stations below), keyed by station id, so the poses are the web UI's.

Not for robots: it is a test tool. Run it next to the agent instead of
master_control, never as well as it.
"""

from __future__ import annotations

import argparse
import math
import threading
import time
from pathlib import Path

import rclpy
import yaml
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import BatteryState
from std_srvs.srv import Trigger

from custom_interfaces.action import MissionPlan
from custom_interfaces.msg import AmrRunData, RobotStatus
from nav2_msgs.action import NavigateToPose

DOCK_S = 3.0
UNDOCK_S = 2.0
NAV_TIMEOUT_S = 600.0


class FakeMasterControl(Node):
    def __init__(self, stations_file: Path, min_battery: float) -> None:
        super().__init__("fake_master_control")
        self._stations_file = stations_file
        self._min_battery = min_battery
        self._cb = ReentrantCallbackGroup()
        self._lock = threading.Lock()
        self._status = 0  # 0 idle, 1 moving, 2 waiting for the operator
        self._docked = False
        self._battery = 100.0
        self._event_index = 0
        self._cycle = 0
        self._confirmed = threading.Event()

        self._status_pub = self.create_publisher(RobotStatus, "/robot_status", 10)
        self._event_pub = self.create_publisher(
            AmrRunData,
            "/amr_run_data",
            QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE),
        )
        self.create_subscription(BatteryState, "/battery_state", self._on_battery, 10)
        self.create_service(
            Trigger, "/confirm_next_mission", self._on_confirm, callback_group=self._cb
        )
        self._nav = ActionClient(
            self, NavigateToPose, "navigate_to_pose", callback_group=self._cb
        )
        ActionServer(
            self,
            MissionPlan,
            "/mission_plan",
            execute_callback=self._execute,
            goal_callback=self._on_goal,
            cancel_callback=lambda _goal: CancelResponse.ACCEPT,
            callback_group=self._cb,
        )
        self.create_timer(1.0, self._publish_status, callback_group=self._cb)
        self.get_logger().info(f"fake master_control up; stations from {stations_file}")

    # ── Status and events, master_control's way ────────────────────────────────

    def _on_battery(self, msg: BatteryState) -> None:
        percentage = float(msg.percentage)
        if not math.isnan(percentage):
            self._battery = percentage * 100.0 if percentage <= 1.0 else percentage

    def _publish_status(self) -> None:
        msg = RobotStatus()
        with self._lock:
            msg.robot_current_sts = self._status
            msg.robot_docked = self._docked
        msg.battery_percentage = float(self._battery)
        self._status_pub.publish(msg)

    def _set_status(self, status: int) -> None:
        with self._lock:
            self._status = status
        self._publish_status()

    def _event(self, name: str, pose=(0.0, 0.0, 0.0)) -> None:
        msg = AmrRunData()
        msg.stamp = self.get_clock().now().to_msg()
        msg.event_index = self._event_index
        self._event_index += 1
        msg.cycle_id = self._cycle
        msg.event_status = name
        msg.goal_x, msg.goal_y = float(pose[0]), float(pose[1])
        msg.goal_qz, msg.goal_qw = math.sin(pose[2] / 2.0), math.cos(pose[2] / 2.0)
        self._event_pub.publish(msg)
        self.get_logger().info(f"[event] {name}")

    # ── /confirm_next_mission ───────────────────────────────────────────────────

    def _on_confirm(self, request, response):
        del request
        with self._lock:
            waiting = self._status == 2
        if not waiting:
            # master_control answers success here too; kept, so the agent's
            # own "only while waiting" check is what is being tried.
            response.success = True
            response.message = "Robot is not currently waiting for verification."
            return response
        self._confirmed.set()
        response.success = True
        response.message = "Mission verified successfully!"
        return response

    # ── /mission_plan ───────────────────────────────────────────────────────────

    def _on_goal(self, goal) -> GoalResponse:
        if self._battery <= self._min_battery:
            self.get_logger().warning(f"rejecting: battery {self._battery:.0f}%")
            return GoalResponse.REJECT
        del goal
        return GoalResponse.ACCEPT

    def _pose_of(self, station_id: str):
        data = yaml.safe_load(self._stations_file.read_text()) or {}
        dock = (data.get("docks") or {}).get(station_id)
        if not dock:
            return None
        x, y, yaw = dock["pose"]
        return float(x), float(y), float(yaw)

    def _execute(self, handle):
        goal = handle.request
        result = MissionPlan.Result()
        feedback = MissionPlan.Feedback()

        def report(stage: str) -> None:
            feedback.mission_sts = stage
            handle.publish_feedback(feedback)

        def finish(ok: bool, text: str):
            self._set_status(0)
            result.result = text
            if handle.is_cancel_requested:
                handle.canceled()
            elif ok:
                handle.succeed()
            else:
                handle.abort()
            return result

        pose = self._pose_of(goal.station_id)
        if pose is None:
            return finish(False, f"FAILED: unknown station {goal.station_id}")

        self._set_status(1)
        report("ON_THE_WAY")
        self._event("STARTED", pose)
        if not self._drive(pose, handle):
            self._event("CANCELED" if handle.is_cancel_requested else "FAILED", pose)
            return finish(False, "FAILED: NAV")

        docking = goal.dest_tasks != 0
        if docking:
            self._event("DOCK_STARTED", pose)
            if not self._hold(DOCK_S, handle):
                return finish(False, "CANCELED")
            with self._lock:
                self._docked = True
            self._event("DOCK_SUCCEEDED", pose)
        else:
            self._event("SUCCEEDED", pose)

        if not goal.continue_mode:
            self._confirmed.clear()
            self._set_status(2)
            report("WAITING_OPERATOR")
            self._event("WAITING_VERIFICATION", pose)
            while not self._confirmed.wait(0.2):
                if handle.is_cancel_requested:
                    break
            if handle.is_cancel_requested:
                self._undock(pose)
                return finish(False, "CANCELED")
            self._event("VERIFIED", pose)
            self._set_status(1)

        if docking:
            self._undock(pose)
        return finish(True, f"SUCCESS: {goal.station_id}")

    def _undock(self, pose) -> None:
        with self._lock:
            docked = self._docked
        if not docked:
            return
        self._event("UNDOCK_STARTED", pose)
        time.sleep(UNDOCK_S)
        with self._lock:
            self._docked = False
        self._event("UNDOCK_SUCCEEDED", pose)

    def _hold(self, seconds: float, handle) -> bool:
        end = time.time() + seconds
        while time.time() < end:
            if handle.is_cancel_requested:
                return False
            time.sleep(0.1)
        return True

    def _drive(self, pose, handle) -> bool:
        if not self._nav.wait_for_server(timeout_sec=10.0):
            self.get_logger().error("navigate_to_pose is not available")
            return False
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose.header.frame_id = "map"
        nav_goal.pose.pose.position.x, nav_goal.pose.pose.position.y = pose[0], pose[1]
        nav_goal.pose.pose.orientation.z = math.sin(pose[2] / 2.0)
        nav_goal.pose.pose.orientation.w = math.cos(pose[2] / 2.0)
        sent = self._nav.send_goal_async(nav_goal)
        end = time.time() + 20.0
        while not sent.done():
            if time.time() > end:
                return False
            time.sleep(0.05)
        nav_handle = sent.result()
        if nav_handle is None or not nav_handle.accepted:
            return False
        done = nav_handle.get_result_async()
        end = time.time() + NAV_TIMEOUT_S
        while not done.done():
            if handle.is_cancel_requested or time.time() > end:
                nav_handle.cancel_goal_async()
                return False
            time.sleep(0.1)
        return done.result().status == 4  # GoalStatus.STATUS_SUCCEEDED


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--stations",
        type=Path,
        default=Path.home() / "amr_agent" / "station_data.yaml",
        help="the dock database the agent writes (its station_file)",
    )
    parser.add_argument("--min-battery", type=float, default=30.0)
    args, ros_args = parser.parse_known_args()
    rclpy.init(args=ros_args)
    node = FakeMasterControl(args.stations, args.min_battery)
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
