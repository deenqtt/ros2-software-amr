#!/usr/bin/env python3
"""
mission_manager_node — Action server /mission_plan + service /dock_command untuk simulasi AMR.

Implements: custom_interfaces/action/MissionPlan
  Goal:
    string station_id   - identifier station tujuan (harus sudah di-register)
    int8 dest_tasks     - 1=Pick, 2=Drop
    bool continue_mode  - true=Auto, false=Manual (tunggu konfirmasi)
  Result:
    string result       - SUCCESS / FAILED / CANCELED
  Feedback:
    string mission_sts  - NAVIGATING(Xm) / ARRIVING(Xm) /
                          EXECUTING_PICK / EXECUTING_DROP /
                          WAITING PAYLOAD / COMPLETED

Service /station_config (custom_interfaces/srv/StationConfig):
  - Register / hapus station dari registry internal
  - action=1 → simpan, action=0 → hapus

Service /dock_command (custom_interfaces/srv/DockCommand):
  - action="dock"   → navigasi ke station lalu publish /dock_status: docked
  - action="undock" → backup mundur lalu publish /dock_status: idle
  - action="cancel" → hentikan docking aktif

Service /mission_confirm (std_srvs/Trigger):
  - Konfirmasi manual saat continue_mode=false

Topic /dock_status (std_msgs/String):
  - idle / navigating_to_dock / docked / undocking / error

NOTE: execute callback MissionPlan sengaja dibuat synchronous (bukan async) karena
MultiThreadedExecutor tidak provide asyncio event loop di thread-nya.
DockCommand dijalankan di background thread supaya service langsung return.
"""

import math
import threading
import time

import rclpy
from rclpy.action import ActionServer, ActionClient, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import String
from std_srvs.srv import Trigger

from custom_interfaces.action import MissionPlan
from custom_interfaces.srv import DockCommand, StationConfig
from custom_interfaces.msg import RobotStatus


class MissionManagerNode(Node):

    TASK_DELAY_SEC   = 1.5    # simulasi delay Pick/Drop
    NAV_TIMEOUT_SEC  = 180.0  # timeout navigasi per waypoint
    POLL_INTERVAL    = 0.05   # detik antar poll
    UNDOCK_BACKUP_M  = 0.5    # jarak mundur saat undock (meter)
    UNDOCK_SPEED     = 0.15   # kecepatan mundur (m/s)

    def __init__(self):
        super().__init__('mission_manager_node')

        self._cb_group = ReentrantCallbackGroup()

        # ── Station registry: station_id → {x, y, yaw} ───────────────────────
        self._stations: dict = {}

        # ── Docking state ─────────────────────────────────────────────────────
        self._dock_cancel  = False
        self._dock_active  = False

        # ── Publishers ────────────────────────────────────────────────────────
        self._dock_status_pub   = self.create_publisher(String,       '/dock_status',   10)
        self._cmd_vel_pub       = self.create_publisher(Twist,        '/cmd_vel',       10)
        self._robot_status_pub  = self.create_publisher(RobotStatus,  '/robot_status',  10)

        # Status code constants (sesuai RobotStatus.msg)
        self.STS_IDLE       = 0
        self.STS_NAVIGATING = 1
        self.STS_DOCKING    = 2
        self.STS_UNDOCKING  = 3
        self.STS_CHARGING   = 4
        self.STS_ERROR      = 5

        # Internal state tracking untuk robot_status
        self._is_docked   = False
        self._is_charging = False

        # ── Action server /mission_plan ───────────────────────────────────────
        self._action_server = ActionServer(
            self,
            MissionPlan,
            '/mission_plan',
            execute_callback=self._execute_cb,
            goal_callback=self._goal_cb,
            cancel_callback=self._cancel_cb,
            callback_group=self._cb_group,
        )

        # ── Nav2 action client ────────────────────────────────────────────────
        self._nav_client = ActionClient(
            self, NavigateToPose, 'navigate_to_pose',
            callback_group=self._cb_group,
        )

        # ── Station config service ────────────────────────────────────────────
        self.create_service(
            StationConfig, '/station_config',
            self._on_station_config,
            callback_group=self._cb_group,
        )

        # ── Dock command service ──────────────────────────────────────────────
        self.create_service(
            DockCommand, '/dock_command',
            self._on_dock_command,
            callback_group=self._cb_group,
        )

        # ── Manual confirm service ────────────────────────────────────────────
        self.create_service(
            Trigger, '/mission_confirm',
            self._on_confirm,
            callback_group=self._cb_group,
        )
        self._waiting_confirm = False
        self._confirmed       = False

        self._publish_dock_status('idle')
        self._publish_robot_status(self.STS_IDLE, docked=False, undocked=True, charging=False)
        self.get_logger().info(
            '[mission_manager] started — /mission_plan action + /dock_command service ready')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _publish_dock_status(self, status: str):
        self._dock_status_pub.publish(String(data=status))

    def _publish_robot_status(self, sts_code: int,
                               docked: bool = None,
                               undocked: bool = None,
                               charging: bool = None):
        """Publish /robot_status agar web-UI bisa update Available/Busy badge."""
        # Gunakan internal state kalau tidak di-override
        is_docked   = self._is_docked   if docked   is None else docked
        is_undocked = (not is_docked)   if undocked is None else undocked
        is_charging = self._is_charging if charging is None else charging

        msg = RobotStatus()
        msg.robot_current_sts = sts_code
        msg.robot_docked      = is_docked
        msg.robot_undocked    = is_undocked
        msg.charging_state    = is_charging
        self._robot_status_pub.publish(msg)
        self.get_logger().debug(
            f'[robot_status] sts={sts_code} docked={is_docked} '
            f'undocked={is_undocked} charging={is_charging}'
        )

    def _build_nav_goal(self, station_id: str) -> NavigateToPose.Goal | None:
        if station_id not in self._stations:
            return None
        st  = self._stations[station_id]
        yaw = st['yaw']
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id    = 'map'
        goal.pose.header.stamp       = self.get_clock().now().to_msg()
        goal.pose.pose.position.x    = st['x']
        goal.pose.pose.position.y    = st['y']
        goal.pose.pose.position.z    = 0.0
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)
        return goal

    def _navigate_to_station(self, station_id: str) -> bool:
        """
        Kirim Nav2 goal ke station, block sampai selesai.
        Return True jika sukses, False jika gagal/cancel.
        """
        nav_goal = self._build_nav_goal(station_id)
        if nav_goal is None:
            self.get_logger().error(f'[dock] Unknown station_id: "{station_id}"')
            return False

        if not self._nav_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('[dock] Nav2 not available')
            return False

        send_future = self._nav_client.send_goal_async(nav_goal)
        deadline = time.time() + 15.0
        while not send_future.done():
            if self._dock_cancel or time.time() > deadline:
                return False
            time.sleep(self.POLL_INTERVAL)

        nav_goal_handle = send_future.result()
        if not nav_goal_handle.accepted:
            self.get_logger().error('[dock] Nav2 goal rejected')
            return False

        result_future = nav_goal_handle.get_result_async()
        deadline = time.time() + self.NAV_TIMEOUT_SEC
        while not result_future.done():
            if self._dock_cancel:
                nav_goal_handle.cancel_goal_async()
                return False
            if time.time() > deadline:
                nav_goal_handle.cancel_goal_async()
                self.get_logger().error('[dock] Navigation timeout')
                return False
            time.sleep(self.POLL_INTERVAL)

        status = result_future.result().status
        return status == GoalStatus.STATUS_SUCCEEDED

    # ── Station config service ────────────────────────────────────────────────

    def _on_station_config(self, request, response):
        sid = request.station_id
        if request.action == 1:  # save
            self._stations[sid] = {
                'x':   request.x_pose,
                'y':   request.y_pose,
                'yaw': request.yaw_pose,
            }
            self.get_logger().info(
                f'[mission_manager] station saved: "{sid}" '
                f'({request.x_pose:.2f}, {request.y_pose:.2f}, yaw={request.yaw_pose:.2f})')
            response.result = f'OK: station "{sid}" saved'
        elif request.action == 0:  # delete
            if sid in self._stations:
                del self._stations[sid]
                self.get_logger().info(f'[mission_manager] station deleted: "{sid}"')
                response.result = f'OK: station "{sid}" deleted'
            else:
                response.result = f'WARN: station "{sid}" not found'
        else:
            response.result = f'ERROR: unknown action {request.action}'
        return response

    # ── Dock command service ──────────────────────────────────────────────────

    def _on_dock_command(self, request, response):
        action = request.action.lower()
        sid    = request.station_id

        if action == 'dock':
            if sid not in self._stations:
                response.result = f'ERROR: Unknown station_id "{sid}"'
                return response
            if self._dock_active:
                response.result = 'ERROR: Docking already in progress'
                return response
            # Jalankan di background thread — service langsung return
            threading.Thread(
                target=self._do_dock, args=(sid,), daemon=True
            ).start()
            response.result = 'OK: docking started'

        elif action == 'undock':
            if self._dock_active:
                response.result = 'ERROR: Cannot undock while docking in progress'
                return response
            threading.Thread(target=self._do_undock, daemon=True).start()
            response.result = 'OK: undocking started'

        elif action == 'cancel':
            self._dock_cancel  = True
            self._dock_active  = False
            self._is_docked    = False
            self._is_charging  = False
            self._publish_dock_status('idle')
            self._publish_robot_status(self.STS_IDLE, docked=False, undocked=True, charging=False)
            self.get_logger().info('[dock] Docking cancelled by request')
            response.result = 'OK: cancelled'

        else:
            response.result = f'ERROR: Unknown dock action "{action}"'

        return response

    def _do_dock(self, station_id: str):
        self._dock_active  = True
        self._dock_cancel  = False
        self._is_docked    = False
        self._is_charging  = False
        self.get_logger().info(f'[dock] Navigating to dock station "{station_id}"')
        self._publish_dock_status('navigating_to_dock')
        self._publish_robot_status(self.STS_DOCKING, docked=False, undocked=True, charging=False)

        success = self._navigate_to_station(station_id)

        if success:
            self.get_logger().info(f'[dock] Docked at "{station_id}"')
            self._is_docked   = True
            self._is_charging = True
            self._publish_dock_status('docked')
            self._publish_robot_status(self.STS_CHARGING, docked=True, undocked=False, charging=True)
        else:
            if not self._dock_cancel:
                self.get_logger().error(f'[dock] Failed to reach station "{station_id}"')
                self._publish_dock_status('error')
                self._publish_robot_status(self.STS_ERROR, docked=False, undocked=True, charging=False)
            else:
                self._publish_dock_status('idle')
                self._publish_robot_status(self.STS_IDLE, docked=False, undocked=True, charging=False)

        self._dock_active = False
        self._dock_cancel = False

    def _do_undock(self):
        self._dock_active  = True
        self._dock_cancel  = False
        self._is_docked    = False
        self._is_charging  = False
        self.get_logger().info('[dock] Undocking — backing up')
        self._publish_dock_status('undocking')
        self._publish_robot_status(self.STS_UNDOCKING, docked=False, undocked=False, charging=False)

        # Mundur selama UNDOCK_BACKUP_M / UNDOCK_SPEED detik
        backup_secs = self.UNDOCK_BACKUP_M / self.UNDOCK_SPEED
        twist = Twist()
        twist.linear.x = -self.UNDOCK_SPEED
        deadline = time.time() + backup_secs
        while time.time() < deadline and not self._dock_cancel:
            self._cmd_vel_pub.publish(twist)
            time.sleep(0.1)

        # Stop
        self._cmd_vel_pub.publish(Twist())
        self.get_logger().info('[dock] Undock complete')
        self._publish_dock_status('idle')
        self._publish_robot_status(self.STS_IDLE, docked=False, undocked=True, charging=False)
        self._dock_active = False
        self._dock_cancel = False

    # ── Goal / Cancel callbacks (MissionPlan) ────────────────────────────────

    def _goal_cb(self, goal_request):
        sid      = goal_request.station_id
        task_str = 'Pick' if goal_request.dest_tasks == 1 else 'Drop'
        mode_str = 'Auto' if goal_request.continue_mode else 'Manual'
        self.get_logger().info(
            f'[mission_manager] goal received: station_id="{sid}"'
            f' task={task_str} mode={mode_str}')
        return GoalResponse.ACCEPT

    def _cancel_cb(self, goal_handle):
        self.get_logger().info('[mission_manager] cancel requested')
        self._confirmed = True  # unblock manual wait
        return CancelResponse.ACCEPT

    # ── Execute (synchronous) ─────────────────────────────────────────────────

    def _execute_cb(self, goal_handle: ServerGoalHandle):
        goal     = goal_handle.request
        feedback = MissionPlan.Feedback()
        sid      = goal.station_id
        task_str = 'Pick' if goal.dest_tasks == 1 else 'Drop'

        def _abort(msg):
            self.get_logger().error(f'[mission_manager] {msg}')
            goal_handle.abort()
            r = MissionPlan.Result(); r.result = f'FAILED: {msg}'; return r

        def _canceled():
            r = MissionPlan.Result(); r.result = 'CANCELED'
            goal_handle.canceled(); return r

        # ── 1. Lookup station ─────────────────────────────────────────────────
        if sid not in self._stations:
            return _abort(f'Unknown station_id: "{sid}"')

        st  = self._stations[sid]
        yaw = st['yaw']

        # ── 2. Wait for Nav2 server ───────────────────────────────────────────
        if not self._nav_client.wait_for_server(timeout_sec=10.0):
            return _abort('Nav2 not available')

        # ── 3. Send navigation goal ───────────────────────────────────────────
        feedback.mission_sts = 'NAVIGATING'
        goal_handle.publish_feedback(feedback)
        self._publish_robot_status(self.STS_NAVIGATING, docked=False, undocked=True, charging=False)

        nav_goal = NavigateToPose.Goal()
        nav_goal.pose = PoseStamped()
        nav_goal.pose.header.frame_id    = 'map'
        nav_goal.pose.header.stamp       = self.get_clock().now().to_msg()
        nav_goal.pose.pose.position.x    = st['x']
        nav_goal.pose.pose.position.y    = st['y']
        nav_goal.pose.pose.position.z    = 0.0
        nav_goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        nav_goal.pose.pose.orientation.w = math.cos(yaw / 2.0)

        send_future = self._nav_client.send_goal_async(
            nav_goal,
            feedback_callback=lambda fb: self._on_nav_feedback(
                goal_handle, fb, feedback),
        )

        deadline = time.time() + 15.0
        while not send_future.done():
            if time.time() > deadline:
                return _abort('Nav2 send_goal timeout')
            time.sleep(self.POLL_INTERVAL)

        nav_goal_handle = send_future.result()
        if not nav_goal_handle.accepted:
            return _abort('nav goal rejected')

        # ── 4. Wait for navigation to complete ────────────────────────────────
        result_future = nav_goal_handle.get_result_async()
        deadline = time.time() + self.NAV_TIMEOUT_SEC

        while not result_future.done():
            if goal_handle.is_cancel_requested:
                nav_goal_handle.cancel_goal_async()
                return _canceled()
            if time.time() > deadline:
                nav_goal_handle.cancel_goal_async()
                return _abort('navigation timeout')
            time.sleep(self.POLL_INTERVAL)

        nav_status = result_future.result().status
        if nav_status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().warn(
                f'[mission_manager] navigation failed (status={nav_status})')
            goal_handle.abort()
            r = MissionPlan.Result()
            r.result = f'FAILED: nav status {nav_status}'
            return r

        self.get_logger().info(
            f'[mission_manager] arrived at "{sid}" → executing {task_str}')

        # ── 5. Execute task (simulasi delay) ──────────────────────────────────
        feedback.mission_sts = f'EXECUTING_{task_str.upper()}'
        goal_handle.publish_feedback(feedback)
        time.sleep(self.TASK_DELAY_SEC)

        # ── 6. Manual confirm mode ────────────────────────────────────────────
        if not goal.continue_mode:
            self.get_logger().info(
                '[mission_manager] Manual mode — waiting /mission_confirm')
            feedback.mission_sts = 'WAITING PAYLOAD'
            goal_handle.publish_feedback(feedback)

            self._confirmed      = False
            self._waiting_confirm = True
            while not self._confirmed:
                if goal_handle.is_cancel_requested:
                    self._waiting_confirm = False
                    return _canceled()
                time.sleep(0.3)
            self._waiting_confirm = False

        # ── 7. Done ───────────────────────────────────────────────────────────
        self.get_logger().info(
            f'[mission_manager] waypoint SUCCEEDED ({task_str}) @ "{sid}"')
        feedback.mission_sts = 'COMPLETED'
        goal_handle.publish_feedback(feedback)
        self._publish_robot_status(self.STS_IDLE, docked=False, undocked=True, charging=False)
        goal_handle.succeed()
        r = MissionPlan.Result(); r.result = 'SUCCESS'; return r

    # ── Nav2 feedback forwarding ──────────────────────────────────────────────

    def _on_nav_feedback(self, goal_handle, nav_fb, feedback):
        dist = nav_fb.feedback.distance_remaining
        if dist < 0.5:
            feedback.mission_sts = f'ARRIVING ({dist:.2f}m)'
        else:
            feedback.mission_sts = f'NAVIGATING ({dist:.2f}m)'
        goal_handle.publish_feedback(feedback)

    # ── Manual confirm service ────────────────────────────────────────────────

    def _on_confirm(self, request, response):
        if self._waiting_confirm:
            self._confirmed = True
            self.get_logger().info('[mission_manager] confirm received → continue')
            response.success = True
            response.message = 'Confirmed'
        else:
            response.success = False
            response.message = 'No waypoint waiting for confirmation'
        return response


# ── Entry point ───────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = MissionManagerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
