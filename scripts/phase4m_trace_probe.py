#!/usr/bin/env python3
"""Continuous production-model trace probe for Phase 4M.

The probe uses simulation time for phase boundaries and independent Gazebo
dynamic-pose JSON for physical ground truth. It never uses /odom as ground
truth and does not modify the model or controller.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock

from phase4k_turn_probe import GroundTruthReader, JointReader, odom_pose
from phase4m_contacts import ContactReader
from phase4m_diagnostics import body_speed_from_samples, find_event_markers, segment_stop_distances


CONTACT_LINKS = {
    "wheel_left": "wheel_left_link/sensor/phase4m_wheel_left_contact",
    "wheel_right": "wheel_right_link/sensor/phase4m_wheel_right_contact",
    "caster_front": "caster_front_link/sensor/phase4m_caster_front_contact",
    "caster_rear": "caster_rear_link/sensor/phase4m_caster_rear_contact",
    "anti_tip_front_left": "stability_front_left_link/sensor/phase4m_anti_tip_front_left_contact",
    "anti_tip_front_right": "stability_front_right_link/sensor/phase4m_anti_tip_front_right_contact",
    "anti_tip_rear_left": "stability_rear_left_link/sensor/phase4m_anti_tip_rear_left_contact",
    "anti_tip_rear_right": "stability_rear_right_link/sensor/phase4m_anti_tip_rear_right_contact",
}
PRIMARY_CONTACTS = ("wheel_left", "wheel_right", "caster_front", "caster_rear")


class TraceProbe(Node):
    def __init__(self, cmd_topic: str, odom_topic: str):
        super().__init__("phase4m_trace_probe")
        self.publisher = self.create_publisher(Twist, cmd_topic, 10)
        self.clock = None
        self.odom = None
        self.ground = None
        self.create_subscription(Odometry, odom_topic, self._odom_callback, 10)
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

    def _odom_callback(self, message):
        self.odom = message

    def _clock_callback(self, message):
        self.clock = message

    def sim_time(self) -> float | None:
        if self.clock is not None:
            return float(self.clock.clock.sec) + float(self.clock.clock.nanosec) * 1e-9
        if self.ground is not None:
            pose = self.ground.snapshot()
            if pose is not None:
                return float(pose["stamp_s"])
        return None

    def wait_ready(self):
        deadline = time.monotonic() + 20.0
        while (self.sim_time() is None or self.odom is None) and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.01)
        if self.sim_time() is None or self.odom is None:
            raise RuntimeError("Timed out waiting for Gazebo simulation time and /odom")

    def publish_command(self, linear_x: float, angular_z: float):
        message = Twist()
        message.linear.x = linear_x
        message.angular.z = angular_z
        self.publisher.publish(message)

    def sample(self, command: dict, ground: GroundTruthReader, joints: JointReader, contacts=None) -> dict:
        sim = self.sim_time()
        if sim is None or self.odom is None:
            raise RuntimeError("Cannot sample before /clock and /odom are ready")
        ground_pose = ground.snapshot()
        odom = odom_pose(self.odom)
        twist = self.odom.twist.twist
        odom_data = {
            "x": odom.x,
            "y": odom.y,
            "z": odom.z,
            "roll": odom.roll,
            "pitch": odom.pitch,
            "yaw": odom.yaw,
            "linear_x_mps": float(twist.linear.x),
            "linear_y_mps": float(twist.linear.y),
            "angular_z_rps": float(twist.angular.z),
        }
        ground_age = None
        if ground_pose is not None:
            ground_age = sim - float(ground_pose.get("stamp_s", sim))
        return {
            "simulation_time_s": sim,
            "wall_time_unix_s": time.time(),
            "command": dict(command),
            "ground": ground_pose,
            "ground_pose_age_s": ground_age,
            "odom": odom_data,
            "joints": joints.snapshot(),
            "contacts": {
                name: reader.snapshot() for name, reader in contacts.items()
            } if contacts is not None else None,
        }

    def run_phase(
        self,
        linear_x: float,
        angular_z: float,
        duration_s: float,
        sample_hz: float,
        ground: GroundTruthReader,
        joints: JointReader,
        contacts=None,
    ) -> list[dict]:
        command = {"linear_x": linear_x, "angular_z": angular_z}
        start = self.sim_time()
        if start is None:
            raise RuntimeError("No simulation time")
        end = start + duration_s
        next_sample = start
        samples = []
        wall_deadline = time.monotonic() + duration_s * 4.0 + 10.0
        while time.monotonic() < wall_deadline:
            self.publish_command(linear_x, angular_z)
            rclpy.spin_once(self, timeout_sec=0.002)
            current = self.sim_time()
            if current is None:
                continue
            if current >= next_sample:
                samples.append(self.sample(command, ground, joints, contacts))
                next_sample += 1.0 / sample_hz
            if current >= end:
                break
        else:
            raise RuntimeError(f"Timed out after {duration_s}s simulation phase")
        self.publish_command(0.0, 0.0)
        return samples


def run_trace(args) -> dict:
    rclpy.init()
    node = TraceProbe(args.cmd_topic, args.odom_topic)
    joints = JointReader(args.joint_topic)
    ground = GroundTruthReader(args.ground_topic, args.model)
    node.ground = ground
    contacts = {}
    if args.contact_root:
        for name, relative_topic in CONTACT_LINKS.items():
            topic = f"{args.contact_root.rstrip('/')}/link/{relative_topic}/contact"
            contacts[name] = ContactReader(topic)
            if name in PRIMARY_CONTACTS:
                contacts[name].wait_ready(timeout_s=3.0)
    try:
        node.wait_ready()
        ground.wait_ready()
        joints_deadline = time.monotonic() + 10.0
        while joints.snapshot() is None and time.monotonic() < joints_deadline:
            rclpy.spin_once(node, timeout_sec=0.01)
        if joints.snapshot() is None:
            raise RuntimeError("Timed out waiting for Gazebo wheel joint state")
        samples = []
        samples.extend(node.run_phase(0.0, 0.0, args.pre_idle_s, args.sample_hz, ground, joints, contacts or None))
        contact_ready = {
            name: reader.snapshot() is not None for name, reader in contacts.items()
        } if contacts else None
        samples.extend(node.run_phase(args.linear_x, args.angular_z, args.active_s, args.sample_hz, ground, joints, contacts or None))
        samples.extend(node.run_phase(0.0, 0.0, args.post_zero_s, args.sample_hz, ground, joints, contacts or None))
        body_speed_from_samples(samples)
        markers = find_event_markers(samples)
        result = {
            "phase": "4M",
            "kind": args.kind,
            "model": args.model,
            "command": {"linear_x": args.linear_x, "angular_z": args.angular_z},
            "sample_hz_requested": args.sample_hz,
            "sample_count": len(samples),
            "simulation_duration_s": samples[-1]["simulation_time_s"] - samples[0]["simulation_time_s"],
            "ground_truth_source": "gz topic --json-output /world/amr_world/dynamic_pose/info",
            "ground_pose_age_max_s": max(
                (sample["ground_pose_age_s"] for sample in samples if sample["ground_pose_age_s"] is not None),
                default=None,
            ),
            "event_markers": markers,
            "stop_distances": segment_stop_distances(samples, markers) if args.kind == "stop" else None,
            "contact_topics_ready": contact_ready,
            "samples": samples,
        }
        return result
    finally:
        for reader in contacts.values():
            reader.close()
        joints.close()
        ground.close()
        node.destroy_node()
        rclpy.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=("turn", "stop"), required=True)
    parser.add_argument("--linear-x", type=float, default=0.0)
    parser.add_argument("--angular-z", type=float, default=0.0)
    parser.add_argument("--active-s", type=float, default=4.0)
    parser.add_argument("--pre-idle-s", type=float, default=1.0)
    parser.add_argument("--post-zero-s", type=float, default=5.0)
    parser.add_argument("--sample-hz", type=float, default=50.0)
    parser.add_argument("--model", default="amr_robot")
    parser.add_argument("--joint-topic", default="/world/amr_world/model/amr_robot/joint_state")
    parser.add_argument("--ground-topic", default="/world/amr_world/dynamic_pose/info")
    parser.add_argument("--cmd-topic", default="/cmd_vel")
    parser.add_argument("--odom-topic", default="/odom")
    parser.add_argument(
        "--contact-root",
        default=None,
        help="Gazebo model contact topic root, e.g. /world/amr_world/model/amr_robot",
    )
    args = parser.parse_args()
    result = run_trace(args)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
