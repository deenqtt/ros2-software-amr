#!/usr/bin/env python3
"""Headless Phase 4G ground-truth versus odometry probe.

Ground truth is queried independently from Gazebo Sim using ``gz model``.
Odometry is sampled from ROS ``/odom``.  The script deliberately does not
derive either value from the other source or modify the odometry message.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock

from phase4g_motion_metrics import compute_motion_metrics, wrap_angle


POSE_RE = re.compile(
    r"Pose \[ XYZ \(m\) \] \[ RPY \(rad\) \]:\s*"
    r"\[([^]]+)\]\s*\[([^]]+)\]",
    re.MULTILINE,
)


def quaternion_yaw(z: float, w: float) -> float:
    return math.atan2(2.0 * w * z, 1.0 - 2.0 * z * z)


@dataclass
class Pose:
    x: float
    y: float
    z: float
    yaw: float


@dataclass
class Trial:
    name: str
    repeat: int
    linear_x: float
    angular_z: float
    duration_s: float
    ground_start: Pose
    ground_final: Pose
    odom_start: Pose
    odom_final: Pose
    ground_delta_xy_m: float
    odom_delta_xy_m: float
    translational_error_m: float
    translational_error_percent: float
    ground_delta_x_m: float
    ground_delta_y_m: float
    odom_delta_x_m: float
    odom_delta_y_m: float
    ground_delta_yaw_deg: float
    odom_delta_yaw_deg: float
    rotational_error_deg: float
    ground_forward_delta_m: float
    ground_lateral_delta_m: float
    odom_forward_delta_m: float
    odom_lateral_delta_m: float
    ground_origin_arc_m: float
    reference_point: str
    raw_world_xy_note: str
    stop_ground_delta_m: float
    stop_odom_linear_mps: float
    stop_odom_angular_rps: float
    wall_elapsed_s: float
    simulation_elapsed_s: float


class MotionProbe(Node):
    def __init__(self, cmd_topic: str, odom_topic: str) -> None:
        super().__init__("phase4g_motion_probe")
        self.publisher = self.create_publisher(Twist, cmd_topic, 10)
        self.last_odom: Odometry | None = None
        self.last_clock: Clock | None = None
        self.subscription = self.create_subscription(
            Odometry, odom_topic, self._odom_callback, 10
        )
        self.clock_subscription = self.create_subscription(
            Clock,
            "/clock",
            self._clock_callback,
            QoSProfile(
                depth=10,
                reliability=ReliabilityPolicy.BEST_EFFORT,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
        )

    def _odom_callback(self, message: Odometry) -> None:
        self.last_odom = message

    def _clock_callback(self, message: Clock) -> None:
        self.last_clock = message

    def spin_for(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.02)

    def wait_for_odom(self, timeout_s: float = 10.0) -> Odometry:
        deadline = time.monotonic() + timeout_s
        while self.last_odom is None and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
        if self.last_odom is None:
            raise RuntimeError("Timed out waiting for /odom")
        return self.last_odom

    @staticmethod
    def clock_seconds(message: Clock) -> float:
        return float(message.clock.sec) + float(message.clock.nanosec) * 1e-9

    def wait_for_clock(self, timeout_s: float = 10.0) -> Clock:
        deadline = time.monotonic() + timeout_s
        while self.last_clock is None and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
        if self.last_clock is None:
            raise RuntimeError("Timed out waiting for /clock")
        return self.last_clock

    def publish_for(
        self, linear_x: float, angular_z: float, duration_s: float
    ) -> tuple[float, float, float, float]:
        command = Twist()
        command.linear.x = float(linear_x)
        command.angular.z = float(angular_z)
        self.wait_for_clock()
        wall_start = time.monotonic()
        simulation_start = self.clock_seconds(self.last_clock)
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            self.publisher.publish(command)
            rclpy.spin_once(self, timeout_sec=0.02)
        wall_elapsed = time.monotonic() - wall_start
        self.spin_for(0.05)
        simulation_end = self.clock_seconds(self.wait_for_clock())
        return wall_elapsed, simulation_end - simulation_start, simulation_start, simulation_end

    def stop_and_settle(self, seconds: float, model: str) -> tuple[Pose, Pose, float, float]:
        self.publisher.publish(Twist())
        self.spin_for(seconds)
        odom = self.wait_for_odom()
        ground_before = query_ground_truth(model)
        self.spin_for(0.5)
        ground_after = query_ground_truth(model)
        return (
            ground_before,
            ground_after,
            math.hypot(odom.twist.twist.linear.x, odom.twist.twist.linear.y),
            abs(odom.twist.twist.angular.z),
        )


def query_ground_truth(model: str = "amr_robot") -> Pose:
    result = subprocess.run(
        ["gz", "model", "-m", model, "-p"],
        check=True,
        capture_output=True,
        text=True,
        timeout=8.0,
    )
    output = result.stdout + result.stderr
    match = POSE_RE.search(output)
    if match is None:
        raise RuntimeError(f"Could not parse Gazebo pose from: {output[-1000:]}")
    xyz = [float(value) for value in match.group(1).split()]
    rpy = [float(value) for value in match.group(2).split()]
    return Pose(xyz[0], xyz[1], xyz[2], rpy[2])


def odom_pose(message: Odometry) -> Pose:
    position = message.pose.pose.position
    orientation = message.pose.pose.orientation
    return Pose(position.x, position.y, position.z, quaternion_yaw(orientation.z, orientation.w))


def run_trial(node: MotionProbe, name: str, repeat: int, linear_x: float, angular_z: float, duration_s: float, model: str) -> Trial:
    node.spin_for(0.2)
    odom_start = odom_pose(node.wait_for_odom())
    ground_start = query_ground_truth(model)
    wall_elapsed, simulation_elapsed, _, _ = node.publish_for(
        linear_x, angular_z, duration_s
    )
    ground_before_stop, ground_after_stop, stop_linear, stop_angular = node.stop_and_settle(0.8, model)
    odom_final = odom_pose(node.wait_for_odom())

    ground_final = ground_before_stop
    ground_dx = ground_final.x - ground_start.x
    ground_dy = ground_final.y - ground_start.y
    odom_dx = odom_final.x - odom_start.x
    odom_dy = odom_final.y - odom_start.y
    metrics = compute_motion_metrics(ground_start, ground_final, odom_start, odom_final)
    return Trial(
        name=name,
        repeat=repeat,
        linear_x=linear_x,
        angular_z=angular_z,
        duration_s=duration_s,
        ground_start=ground_start,
        ground_final=ground_final,
        odom_start=odom_start,
        odom_final=odom_final,
        ground_delta_xy_m=metrics.ground_delta_xy_m,
        odom_delta_xy_m=metrics.odom_delta_xy_m,
        translational_error_m=metrics.translational_error_m,
        translational_error_percent=metrics.translational_error_percent,
        ground_delta_x_m=metrics.ground_delta_x_m,
        ground_delta_y_m=metrics.ground_delta_y_m,
        odom_delta_x_m=metrics.odom_delta_x_m,
        odom_delta_y_m=metrics.odom_delta_y_m,
        ground_delta_yaw_deg=metrics.ground_delta_yaw_deg,
        odom_delta_yaw_deg=metrics.odom_delta_yaw_deg,
        rotational_error_deg=metrics.rotational_error_deg,
        ground_forward_delta_m=metrics.ground_forward_delta_m,
        ground_lateral_delta_m=metrics.ground_lateral_delta_m,
        odom_forward_delta_m=metrics.odom_forward_delta_m,
        odom_lateral_delta_m=metrics.odom_lateral_delta_m,
        ground_origin_arc_m=metrics.ground_origin_arc_m,
        reference_point=metrics.reference_point,
        raw_world_xy_note=metrics.raw_world_xy_note,
        stop_ground_delta_m=math.hypot(
            ground_after_stop.x - ground_before_stop.x,
            ground_after_stop.y - ground_before_stop.y,
        ),
        stop_odom_linear_mps=stop_linear,
        stop_odom_angular_rps=stop_angular,
        wall_elapsed_s=wall_elapsed,
        simulation_elapsed_s=simulation_elapsed,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="amr_robot")
    parser.add_argument("--cmd-topic", default="/cmd_vel")
    parser.add_argument("--odom-topic", default="/odom")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--duration-linear", type=float, default=5.0)
    parser.add_argument("--duration-angular", type=float, default=4.0)
    args = parser.parse_args()

    tests = [
        ("T1_FORWARD", 0.20, 0.0, args.duration_linear),
        ("T2_REVERSE", -0.20, 0.0, args.duration_linear),
        ("T3_CCW", 0.0, 0.40, args.duration_angular),
        ("T4_CW", 0.0, -0.40, args.duration_angular),
    ]
    rclpy.init()
    node = MotionProbe(args.cmd_topic, args.odom_topic)
    trials: list[Trial] = []
    try:
        node.wait_for_odom()
        node.wait_for_clock()
        for name, linear_x, angular_z, duration_s in tests:
            for repeat in range(1, args.repeats + 1):
                trial = run_trial(node, name, repeat, linear_x, angular_z, duration_s, args.model)
                trials.append(trial)
                print(json.dumps(asdict(trial), sort_keys=True), flush=True)
        zero_ground_start, zero_ground_final, stop_linear, stop_angular = node.stop_and_settle(2.0, args.model)
        stop_result = {
            "name": "T5_STOP",
            "ground_start": asdict(zero_ground_start),
            "ground_final": asdict(zero_ground_final),
            "ground_delta_m": math.hypot(
                zero_ground_final.x - zero_ground_start.x,
                zero_ground_final.y - zero_ground_start.y,
            ),
            "odom_linear_mps": stop_linear,
            "odom_angular_rps": stop_angular,
        }
        print(json.dumps(stop_result, sort_keys=True), flush=True)
        result = {
            "generated_at_unix": time.time(),
            "model": args.model,
            "ground_truth_command": f"gz model -m {args.model} -p",
            "tests": [asdict(trial) for trial in trials],
            "stop": stop_result,
        }
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
