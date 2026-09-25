#!/usr/bin/env python3
"""High-resolution Gazebo/ROS turn and stop diagnostics for Phase 4K."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import threading
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock

from phase4g_motion_metrics import wrap_angle
from phase4k_diagnostics import (
    expected_wheel_omega,
    parse_dynamic_pose_block,
    parse_dynamic_pose_json_line,
    parse_joint_state_block,
    simulation_window_deadline,
)


class Pose:
    def __init__(self, x, y, z, roll, pitch, yaw):
        self.x, self.y, self.z = x, y, z
        self.roll, self.pitch, self.yaw = roll, pitch, yaw


def _quat_rpy(x: float, y: float, z: float, w: float) -> tuple[float, float, float]:
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch_arg = 2 * (w * y - z * x)
    pitch = math.asin(max(-1.0, min(1.0, pitch_arg)))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


def query_ground_truth(model: str) -> Pose:
    result = subprocess.run(
        ["gz", "model", "-m", model, "-p"],
        check=True,
        capture_output=True,
        text=True,
        timeout=8.0,
    )
    lines = result.stdout.splitlines()
    xyz = rpy = None
    for index, line in enumerate(lines):
        if "[ XYZ (m) ] [ RPY (rad) ]:" in line:
            xyz = [float(v) for v in lines[index + 1].strip().strip("[]").split()]
            rpy = [float(v) for v in lines[index + 2].strip().strip("[]").split()]
            break
    if xyz is None or rpy is None:
        raise RuntimeError(f"Could not parse Gazebo pose: {result.stdout[-1000:]}")
    return Pose(xyz[0], xyz[1], xyz[2], rpy[0], rpy[1], rpy[2])


def odom_pose(message: Odometry) -> Pose:
    p = message.pose.pose.position
    q = message.pose.pose.orientation
    roll, pitch, yaw = _quat_rpy(q.x, q.y, q.z, q.w)
    return Pose(p.x, p.y, p.z, roll, pitch, yaw)


class JointReader:
    def __init__(self, topic: str):
        self.latest = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._process = subprocess.Popen(
            ["stdbuf", "-oL", "gz", "topic", "-e", "-t", topic],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self):
        block = []
        assert self._process.stdout is not None
        for line in self._process.stdout:
            if self._stop.is_set():
                break
            if line.lstrip().startswith("header {") and block:
                self._consume(block)
                block = []
            if line.strip():
                block.append(line)
            elif block:
                self._consume(block)
                block = []
        if block:
            self._consume(block)

    def _consume(self, lines):
        try:
            parsed = parse_joint_state_block("".join(lines))
        except ValueError:
            return
        with self._lock:
            self.latest = parsed

    def snapshot(self):
        with self._lock:
            return self.latest

    def close(self):
        self._stop.set()
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()


class GroundTruthReader:
    """Read the newest JSON-formatted Gazebo pose message."""

    def __init__(self, topic: str, model: str):
        self.topic = topic
        self.model = model
        self.latest = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._process = subprocess.Popen(
            ["stdbuf", "-oL", "gz", "topic", "-e", "--json-output", "-t", topic],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self):
        assert self._process.stdout is not None
        for line in self._process.stdout:
            if self._stop.is_set():
                break
            try:
                parsed = parse_dynamic_pose_json_line(line, self.model)
            except (ValueError, TypeError):
                continue
            with self._lock:
                parsed["source"] = "gz topic --json-output dynamic_pose/info"
                self.latest = parsed

    def snapshot(self):
        with self._lock:
            return dict(self.latest) if self.latest is not None else None

    def wait_ready(self):
        deadline = time.monotonic() + 30.0
        while self.latest is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if self.latest is None:
            raise RuntimeError(f"Timed out waiting for live Gazebo dynamic pose for {self.model}")

    def close(self):
        self._stop.set()
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()


class Probe(Node):
    def __init__(self, cmd_topic: str, odom_topic: str):
        super().__init__("phase4k_turn_probe")
        self.publisher = self.create_publisher(Twist, cmd_topic, 10)
        self.odom = None
        self.clock = None
        self.create_subscription(Odometry, odom_topic, self._odom, 10)
        self.create_subscription(
            Clock,
            "/clock",
            self._clock_callback,
            QoSProfile(
                depth=10,
                reliability=ReliabilityPolicy.BEST_EFFORT,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
        )

    def _odom(self, message):
        self.odom = message

    def _clock_callback(self, message):
        self.clock = message

    def sim_time(self):
        if self.clock is None:
            return None
        return float(self.clock.clock.sec) + float(self.clock.clock.nanosec) * 1e-9

    def wait_ready(self):
        deadline = time.monotonic() + 10
        while (self.odom is None or self.clock is None) and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.02)
        if self.odom is None or self.clock is None:
            raise RuntimeError("Timed out waiting for /odom and /clock")

    def publish_for(self, linear: float, angular: float, duration: float):
        command = Twist()
        command.linear.x = linear
        command.angular.z = angular
        end = time.monotonic() + duration
        while time.monotonic() < end:
            self.publisher.publish(command)
            rclpy.spin_once(self, timeout_sec=0.01)

    def publish_until_sim(self, linear: float, angular: float, deadline: float):
        command = Twist()
        command.linear.x = linear
        command.angular.z = angular
        wall_deadline = time.monotonic() + 10.0
        while time.monotonic() < wall_deadline:
            current = self.sim_time()
            if current is not None and current >= deadline:
                return
            self.publisher.publish(command)
            rclpy.spin_once(self, timeout_sec=0.01)
        raise RuntimeError(f"Timed out reaching simulation-time window {deadline}")

    def publish_zero(self):
        self.publisher.publish(Twist())
        rclpy.spin_once(self, timeout_sec=0.01)

    @staticmethod
    def set_world_paused(paused: bool):
        request = "pause: true" if paused else "pause: false"
        subprocess.run(
            [
                "gz", "service", "-s", "/world/amr_world/control",
                "--reqtype", "gz.msgs.WorldControl",
                "--reptype", "gz.msgs.Boolean",
                "--req", request, "--timeout", "2000",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=4.0,
        )

    def sample(
        self,
        label: str,
        started_wall: float,
        ground: GroundTruthReader,
        joints: JointReader,
    ):
        ground_query_start = time.monotonic()
        ground_pose = ground.snapshot()
        ground_query_elapsed = time.monotonic() - ground_query_start
        odom = odom_pose(self.odom) if self.odom is not None else None
        simulation_time = self.sim_time()
        ground_pose_age = None
        if simulation_time is not None and ground_pose is not None:
            ground_pose_age = simulation_time - ground_pose.get("stamp_s", simulation_time)
        return {
            "label": label,
            "wall_from_segment_start_s": time.monotonic() - started_wall,
            "simulation_time_s": simulation_time,
            "ground": ground_pose,
            "ground_pose_age_s": ground_pose_age,
            "ground_query_elapsed_s": ground_query_elapsed,
            "odom": vars(odom) if odom else None,
            "joints": joints.snapshot(),
        }


def run_segment(
    node: Probe,
    ground: GroundTruthReader,
    joints: JointReader,
    model: str,
    name: str,
    linear: float,
    angular: float,
    duration: float,
):
    node.wait_ready()
    ground.wait_ready()
    segment_start_wall = time.monotonic()
    segment_start_sim = node.sim_time()
    assert segment_start_sim is not None
    samples = [node.sample("before_command", segment_start_wall, ground, joints)]
    windows = (0.25, 0.5, 1.0, 2.0, duration)
    for target in windows:
        node.publish_until_sim(
            linear, angular, simulation_window_deadline(segment_start_sim, target)
        )
        samples.append(node.sample(f"command_{target:.2f}s", segment_start_wall, ground, joints))

    zero_wall = time.monotonic()
    zero_sim = node.sim_time()
    assert zero_sim is not None
    node.publish_zero()
    samples.append(node.sample("first_zero_command", segment_start_wall, ground, joints))
    for target in (0.25, 0.5, 1.0, 2.0):
        node.publish_until_sim(
            0.0, 0.0, simulation_window_deadline(zero_sim, target)
        )
        samples.append(node.sample(f"zero_{target:.2f}s", segment_start_wall, ground, joints))
    return {
        "name": name,
        "command_linear_x": linear,
        "command_angular_z": angular,
        "expected_wheel_omega": expected_wheel_omega(linear, angular, 0.42, 0.09),
        "first_zero_wall_unix": time.time(),
        "first_zero_segment_wall_s": zero_wall - segment_start_wall,
        "first_zero_simulation_time_s": zero_sim,
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="amr_robot")
    parser.add_argument("--joint-topic", default="/world/amr_world/model/amr_robot/joint_state")
    parser.add_argument("--ground-topic", default="/world/amr_world/dynamic_pose/info")
    parser.add_argument("--cmd-topic", default="/cmd_vel")
    parser.add_argument("--odom-topic", default="/odom")
    args = parser.parse_args()

    rclpy.init()
    node = Probe(args.cmd_topic, args.odom_topic)
    reader = JointReader(args.joint_topic)
    ground = GroundTruthReader(args.ground_topic, args.model)
    try:
        result = {
            "model": args.model,
            "ground_truth": f"gz model -m {args.model} -p",
            "joint_topic": args.joint_topic,
            "segments": [
                run_segment(node, ground, reader, args.model, "FORWARD", 0.20, 0.0, 5.0),
                run_segment(node, ground, reader, args.model, "REVERSE", -0.20, 0.0, 5.0),
                run_segment(node, ground, reader, args.model, "CCW", 0.0, 0.40, 4.0),
                run_segment(node, ground, reader, args.model, "CW", 0.0, -0.40, 4.0),
            ],
        }
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2), flush=True)
    finally:
        reader.close()
        ground.close()
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
