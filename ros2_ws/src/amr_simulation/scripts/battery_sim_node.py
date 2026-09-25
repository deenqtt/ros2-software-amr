#!/usr/bin/env python3
"""
battery_sim_node — Simulasi baterai AMR untuk Gazebo.

Drain rate:
  - Idle  : 0.5 % / menit
  - Moving: 2.0 % / menit  (dihitung dari /odom velocity)

Charge rate:
  - Docked: 5.0 % / menit  (dikontrol oleh /dock_status)

Publish: /battery_state  (sensor_msgs/BatteryState)
         /battery_percent (std_msgs/Float32)  ← mudah dibaca UI
"""

import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Float32, String
from nav_msgs.msg import Odometry


class BatterySimNode(Node):
    def __init__(self):
        super().__init__('battery_sim_node')

        # ── Parameters ────────────────────────────────────────────────────────
        self.declare_parameter('initial_percent',       100.0)  # 0–100
        self.declare_parameter('drain_rate_idle',         0.5)  # %/menit
        self.declare_parameter('drain_rate_moving',       2.0)  # %/menit
        self.declare_parameter('charge_rate',             5.0)  # %/menit
        self.declare_parameter('low_battery_threshold',  20.0)  # %
        self.declare_parameter('moving_threshold',        0.02) # m/s

        self._pct       = self.get_parameter('initial_percent').value
        self._velocity  = 0.0   # m/s (linear + angular contribution)
        self._is_docked = False

        # ── Subscribers ───────────────────────────────────────────────────────
        self.create_subscription(Odometry, '/odom',        self._odom_cb, 10)
        self.create_subscription(String,   '/dock_status', self._dock_cb, 10)

        # ── Publishers ────────────────────────────────────────────────────────
        self._pub_state   = self.create_publisher(BatteryState, '/battery_state',   10)
        self._pub_percent = self.create_publisher(Float32,      '/battery_percent',  10)

        # ── Timer: update 1 Hz ────────────────────────────────────────────────
        self.create_timer(1.0, self._tick)

        self.get_logger().info(
            f'[battery_sim] started — initial: {self._pct:.1f}%'
        )

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _odom_cb(self, msg: Odometry):
        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        wz = msg.twist.twist.angular.z
        # angular velocity contributes sedikit ke drain
        self._velocity = math.sqrt(vx ** 2 + vy ** 2) + abs(wz) * 0.05

    def _dock_cb(self, msg: String):
        self._is_docked = (msg.data.upper() == 'DOCKED')

    # ── Main tick ─────────────────────────────────────────────────────────────

    def _tick(self):
        moving_thr  = self.get_parameter('moving_threshold').value
        drain_idle  = self.get_parameter('drain_rate_idle').value
        drain_move  = self.get_parameter('drain_rate_moving').value
        charge_rate = self.get_parameter('charge_rate').value
        low_thr     = self.get_parameter('low_battery_threshold').value

        is_moving = self._velocity > moving_thr

        if self._is_docked:
            # Charging
            delta = charge_rate / 60.0        # per second
            self._pct = min(100.0, self._pct + delta)
        else:
            # Draining
            rate  = drain_move if is_moving else drain_idle
            delta = rate / 60.0
            self._pct = max(0.0, self._pct - delta)

        # Low battery warning (throttled tiap 30 detik)
        if self._pct <= low_thr and not self._is_docked:
            self.get_logger().warn(
                f'[battery_sim] LOW BATTERY: {self._pct:.1f}%',
                throttle_duration_sec=30.0,
            )

        self._publish()

    def _publish(self):
        now = self.get_clock().now().to_msg()

        # sensor_msgs/BatteryState
        bs = BatteryState()
        bs.header.stamp         = now
        bs.percentage           = self._pct / 100.0          # 0.0–1.0
        bs.voltage              = 12.0
        bs.current              = 2.0 if self._is_docked else -1.0
        bs.charge               = float('nan')
        bs.capacity             = float('nan')
        bs.design_capacity      = float('nan')
        bs.power_supply_status  = (
            BatteryState.POWER_SUPPLY_STATUS_CHARGING
            if self._is_docked
            else BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        )
        bs.power_supply_health      = BatteryState.POWER_SUPPLY_HEALTH_GOOD
        bs.power_supply_technology  = BatteryState.POWER_SUPPLY_TECHNOLOGY_LIPO
        bs.present = True
        self._pub_state.publish(bs)

        # std_msgs/Float32 — persentase langsung, mudah dibaca UI
        pct_msg = Float32()
        pct_msg.data = float(self._pct)
        self._pub_percent.publish(pct_msg)


def main(args=None):
    rclpy.init(args=args)
    node = BatterySimNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
