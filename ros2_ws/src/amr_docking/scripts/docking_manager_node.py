#!/usr/bin/env python3
"""
docking_manager_node — State machine docking AMR (simulasi, ArUco-guided).

Service /dock_command (custom_interfaces/srv/DockCommand):
  Request : { action, station_id, station_name }
  Response: { result: string }

Service /station_config (custom_interfaces/srv/StationConfig):
  Register / hapus station di registry node ini.

State machine:
  IDLE
    ↓ dock command
  NAVIGATING_TO_APPROACH  ← Nav2 ke approach point (hadap dok dari depan)
    ↓ arrived
  NAVIGATING_TO_DOCK      ← mundur pakai cmd_vel, dipandu ArUco marker
    ↓ marker terlalu dekat (< DOCK_DIST_THRESHOLD) atau timeout
  DOCKED
    ↓ undock command
  UNDOCKING               ← Nav2 kembali ke approach point
    ↓ arrived
  IDLE

ArUco guidance (saat NAVIGATING_TO_DOCK):
  - Subscribe /aruco/distance       (Float32) — Z depth ke marker
  - Subscribe /aruco/lateral_offset (Float32) — X offset kamera (+ = kanan kamera)
  - Loop 10 Hz:
      • Kirim cmd_vel mundur konstan -REVERSE_SPEED m/s
      • Koreksi angular proporsional terhadap lateral_offset
        (karena kamera di belakang robot dan robot mundur, offset positif
         berarti marker geser ke kanan kamera → robot perlu belok kanan)
      • Stop saat distance ≤ DOCK_DIST_THRESHOLD ATAU ArUco hilang > ARUCO_LOST_TIMEOUT s
      • Hard timeout: REVERSE_TIMEOUT s

Fallback (ArUco tidak terdeteksi): odom-distance tracking seperti sebelumnya.
"""

import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import String, Float32
from custom_interfaces.srv import DockCommand, StationConfig


# ── Constants ─────────────────────────────────────────────────────────────────

class State:
    IDLE                   = 'IDLE'
    NAVIGATING_TO_APPROACH = 'NAVIGATING_TO_APPROACH'
    NAVIGATING_TO_DOCK     = 'NAVIGATING_TO_DOCK'
    DOCKED                 = 'DOCKED'
    UNDOCKING              = 'UNDOCKING'
    ERROR                  = 'ERROR'

REVERSE_SPEED        = 0.12   # m/s — slow for precision
DOCK_DIST_THRESHOLD  = 0.15   # metres — ArUco Z distance → declare DOCKED
ANGULAR_KP           = 1.2    # proportional gain for lateral correction
MAX_ANGULAR          = 0.4    # rad/s clamp
REVERSE_TIMEOUT      = 30.0   # seconds hard limit
ARUCO_LOST_TIMEOUT   = 3.0    # seconds — fallback to odom if marker unseen


class DockingManagerNode(Node):
    def __init__(self):
        super().__init__('docking_manager_node')

        self._state            = State.IDLE
        self._station          = None
        self._station_registry = {}
        self._current_pose     = None   # (x, y, theta) from amcl_pose
        self._nav_goal_handle  = None

        # ── Reverse / ArUco state ─────────────────────────────────────────────
        self._reverse_timer        = None
        self._reverse_start        = None   # rclpy.Time
        self._odom_start           = None   # (x, y) at reverse start
        self._odom_traveled        = 0.0
        self._reverse_initial_dist = 0.0    # approach→dock distance (fallback)

        # ArUco readings (updated from topic callbacks)
        self._aruco_distance       = None   # float, metres
        self._aruco_lateral        = None   # float, metres (+right in camera)
        self._aruco_last_seen      = None   # rclpy.Time of last detection

        # ── Subscribers ───────────────────────────────────────────────────────
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self._on_pose, 10)
        self.create_subscription(
            Odometry, '/odom', self._on_odom, 10)
        self.create_subscription(
            Float32, '/aruco/distance',       self._on_aruco_distance, 10)
        self.create_subscription(
            Float32, '/aruco/lateral_offset', self._on_aruco_lateral,  10)

        # ── Services ──────────────────────────────────────────────────────────
        self.create_service(DockCommand,   '/dock_command',   self._on_dock_command)
        self.create_service(StationConfig, '/station_config', self._on_station_config)

        # ── Publishers ────────────────────────────────────────────────────────
        self._status_pub  = self.create_publisher(String, '/dock_status', 10)
        self._cmd_vel_pub = self.create_publisher(Twist,  '/cmd_vel',     10)

        # ── Lifecycle client for collision_monitor ────────────────────────────
        self._cm_client = self.create_client(
            ChangeState, '/collision_monitor/change_state')

        # ── Nav2 action client ────────────────────────────────────────────────
        self._nav = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        self.create_timer(1.0, self._publish_status)

        self.get_logger().info(
            '[docking_manager] started — ArUco-guided docking active')

    # ── ArUco callbacks ───────────────────────────────────────────────────────

    def _on_aruco_distance(self, msg: Float32):
        self._aruco_distance  = msg.data
        self._aruco_last_seen = self.get_clock().now()

    def _on_aruco_lateral(self, msg: Float32):
        self._aruco_lateral = msg.data

    # ── Pose / odom callbacks ─────────────────────────────────────────────────

    def _on_pose(self, msg: PoseWithCovarianceStamped):
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self._current_pose = (x, y, math.atan2(siny, cosy))

    def _on_odom(self, msg: Odometry):
        if self._state != State.NAVIGATING_TO_DOCK:
            return
        ox = msg.pose.pose.position.x
        oy = msg.pose.pose.position.y
        if self._odom_start is None:
            self._odom_start = (ox, oy)
        self._odom_traveled = math.sqrt(
            (ox - self._odom_start[0]) ** 2 +
            (oy - self._odom_start[1]) ** 2
        )

    # ── Service handlers ──────────────────────────────────────────────────────

    def _on_dock_command(self, request: DockCommand.Request, response: DockCommand.Response):
        action     = request.action
        station_id = request.station_id
        self.get_logger().info(
            f'[docking_manager] dock_command: action={action} id={station_id}')

        if action == 'dock':
            if self._state not in (State.IDLE, State.ERROR):
                response.result = f'WARN: ignoring dock — state={self._state}'
                return response

            station = self._station_registry.get(station_id)
            if not station:
                response.result = f'ERROR: station id={station_id} not registered'
                return response

            self._station = station
            self._do_approach()
            response.result = 'OK: docking started'

        elif action == 'undock':
            if self._state != State.DOCKED:
                response.result = f'WARN: ignoring undock — state={self._state}'
                return response
            self._do_undock()
            response.result = 'OK: undocking started'

        elif action == 'cancel':
            self._cancel_nav()
            self._stop_reverse()
            self._set_state(State.IDLE)
            response.result = 'OK: cancelled'

        else:
            response.result = f'ERROR: unknown action {action}'

        return response

    def _on_station_config(self, request: StationConfig.Request, response: StationConfig.Response):
        action_str = 'save' if request.action == 1 else 'delete'

        if request.action == 1:
            self._station_registry[request.id] = {
                'target':   {'x': request.x_pose,     'y': request.y_pose,     'yaw': request.yaw_pose},
                'approach': {'x': request.x_approach,  'y': request.y_approach,  'yaw': request.yaw_approach},
            }
            self.get_logger().info(
                f'[docking_manager] station_config save: id={request.id} name="{request.name}"'
                f' pos=({request.x_pose:.2f},{request.y_pose:.2f})')
        else:
            self._station_registry.pop(request.id, None)
            self.get_logger().info(
                f'[docking_manager] station_config delete: id={request.id}')

        response.result = f'OK: {action_str} "{request.name}"'
        return response

    # ── Docking phases ────────────────────────────────────────────────────────

    def _do_approach(self):
        approach = self._station['approach']
        ax, ay   = approach['x'], approach['y']
        ayaw     = approach.get('yaw', 0.0)
        target   = self._station['target']
        tx, ty   = target['x'], target['y']

        if ax != tx or ay != ty:
            self.get_logger().info(
                f'[docking_manager] → approach ({ax:.2f}, {ay:.2f})')
            self._set_state(State.NAVIGATING_TO_APPROACH)
            self._navigate(ax, ay, ayaw,
                           on_success=self._do_dock,
                           on_failure=lambda: self._set_state(State.ERROR))
        else:
            self._do_dock()

    def _do_dock(self):
        target = self._station['target']
        tx, ty = target['x'], target['y']
        self.get_logger().info(
            f'[docking_manager] → reverse to dock ({tx:.2f}, {ty:.2f}) — ArUco guided')
        self._set_state(State.NAVIGATING_TO_DOCK)
        self._start_reverse(tx, ty)

    def _do_undock(self):
        approach = self._station['approach']
        ax, ay   = approach['x'], approach['y']
        target   = self._station['target']

        if ax == target['x'] and ay == target['y']:
            if self._current_pose:
                cx, cy, ct = self._current_pose
                ax = cx - math.cos(ct) * 0.5
                ay = cy - math.sin(ct) * 0.5
            else:
                ax = target['x']
                ay = target['y'] + 0.5

        self.get_logger().info(
            f'[docking_manager] undocking → ({ax:.2f}, {ay:.2f})')
        self._set_state(State.UNDOCKING)
        self._navigate(ax, ay, 0.0,
                       on_success=lambda: self._set_state(State.IDLE),
                       on_failure=lambda: self._set_state(State.IDLE))

    # ── Reverse control ───────────────────────────────────────────────────────

    def _set_collision_monitor(self, activate: bool):
        if not self._cm_client.service_is_ready():
            self.get_logger().warn('[docking_manager] collision_monitor service not ready')
            return
        req = ChangeState.Request()
        req.transition.id = (Transition.TRANSITION_ACTIVATE
                             if activate else Transition.TRANSITION_DEACTIVATE)
        self._cm_client.call_async(req)

    def _start_reverse(self, tx, ty):
        self._set_collision_monitor(False)

        self._reverse_start    = self.get_clock().now()
        self._odom_start       = None
        self._odom_traveled    = 0.0
        self._aruco_last_seen  = None

        if self._current_pose:
            cx, cy, _ = self._current_pose
            self._reverse_initial_dist = math.sqrt((cx - tx) ** 2 + (cy - ty) ** 2)
        else:
            self._reverse_initial_dist = 999.0

        self.get_logger().info(
            f'[docking_manager] reverse start: initial_dist={self._reverse_initial_dist:.2f}m')

        self._reverse_timer = self.create_timer(0.1, self._reverse_tick)

    def _reverse_tick(self):
        if self._state != State.NAVIGATING_TO_DOCK:
            self._stop_reverse()
            return

        now     = self.get_clock().now()
        elapsed = (now - self._reverse_start).nanoseconds / 1e9

        # Hard timeout
        if elapsed > REVERSE_TIMEOUT:
            self.get_logger().error(
                f'[docking_manager] reverse timeout ({elapsed:.1f}s) → ERROR')
            self._stop_reverse()
            self._set_state(State.ERROR)
            return

        # ── ArUco-guided control ──────────────────────────────────────────────
        aruco_age = float('inf')
        if self._aruco_last_seen is not None:
            aruco_age = (now - self._aruco_last_seen).nanoseconds / 1e9

        if aruco_age < ARUCO_LOST_TIMEOUT and self._aruco_distance is not None:
            dist    = self._aruco_distance
            lateral = self._aruco_lateral if self._aruco_lateral is not None else 0.0

            self.get_logger().debug(
                f'[docking_manager] ArUco: dist={dist:.3f}m  lateral={lateral:.3f}m')

            if dist <= DOCK_DIST_THRESHOLD:
                self.get_logger().info(
                    f'[docking_manager] ArUco dist={dist:.3f}m ≤ threshold → DOCKED')
                self._stop_reverse()
                self._on_docked()
                return

            # Proportional angular correction.
            # Camera +X = right in image. Robot is reversing (back toward dock).
            # When camera sees marker offset to the left (lateral < 0), robot
            # should yaw left to re-centre → angular.z positive.
            # Negate lateral because reversing flips the effective steering direction.
            angular = -ANGULAR_KP * lateral
            angular = max(-MAX_ANGULAR, min(MAX_ANGULAR, angular))

            twist = Twist()
            twist.linear.x  = -REVERSE_SPEED
            twist.angular.z = angular
            self._cmd_vel_pub.publish(twist)

        else:
            # ── Fallback: odom-distance (ArUco not visible yet) ───────────────
            if aruco_age >= ARUCO_LOST_TIMEOUT and self._aruco_last_seen is not None:
                self.get_logger().warn(
                    f'[docking_manager] ArUco lost for {aruco_age:.1f}s → odom fallback')

            stop_at = max(self._reverse_initial_dist - DOCK_DIST_THRESHOLD, 0.0)
            if self._odom_traveled >= stop_at:
                self.get_logger().info(
                    f'[docking_manager] odom fallback: traveled={self._odom_traveled:.3f}m → DOCKED')
                self._stop_reverse()
                self._on_docked()
                return

            twist = Twist()
            twist.linear.x = -REVERSE_SPEED
            self._cmd_vel_pub.publish(twist)

    def _stop_reverse(self):
        if self._reverse_timer:
            self._reverse_timer.cancel()
            self._reverse_timer = None
        self._odom_start           = None
        self._odom_traveled        = 0.0
        self._reverse_initial_dist = 0.0
        self._aruco_last_seen      = None
        self._aruco_distance       = None
        self._aruco_lateral        = None
        self._cmd_vel_pub.publish(Twist())
        self._set_collision_monitor(True)

    def _on_docked(self):
        self.get_logger().info('[docking_manager] ✓ DOCKED')
        self._set_state(State.DOCKED)

    # ── Nav2 helper ───────────────────────────────────────────────────────────

    def _navigate(self, x, y, theta, on_success, on_failure):
        if not self._nav.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('[docking_manager] Nav2 server not available')
            on_failure()
            return

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id    = 'map'
        goal.pose.header.stamp       = self.get_clock().now().to_msg()
        goal.pose.pose.position.x    = float(x)
        goal.pose.pose.position.y    = float(y)
        goal.pose.pose.orientation.z = math.sin(theta / 2.0)
        goal.pose.pose.orientation.w = math.cos(theta / 2.0)

        future = self._nav.send_goal_async(goal)

        def _on_goal(future):
            handle = future.result()
            if not handle.accepted:
                self.get_logger().error('[docking_manager] nav goal rejected')
                on_failure()
                return
            self._nav_goal_handle = handle
            handle.get_result_async().add_done_callback(lambda f: _on_result(f))

        def _on_result(future):
            status = future.result().status
            if status == GoalStatus.STATUS_SUCCEEDED:
                on_success()
            else:
                self.get_logger().warn(f'[docking_manager] nav goal failed (status={status})')
                on_failure()

        future.add_done_callback(_on_goal)

    def _cancel_nav(self):
        if self._nav_goal_handle:
            self._nav_goal_handle.cancel_goal_async()
            self._nav_goal_handle = None

    # ── Status ────────────────────────────────────────────────────────────────

    def _set_state(self, state: str):
        self._state = state
        self.get_logger().info(f'[docking_manager] state → {state}')
        self._publish_status()

    def _publish_status(self):
        msg = String()
        msg.data = self._state
        self._status_pub.publish(msg)


# ── Entry point ───────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = DockingManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
