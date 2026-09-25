#!/usr/bin/env python3
"""Focused tests for Phase 4K wheel telemetry parsing and kinematics."""

import math

from phase4k_diagnostics import (
    expected_wheel_omega,
    expected_pure_turn_wheel_omega,
    parse_dynamic_pose_block,
    parse_dynamic_pose_json_line,
    parse_joint_state_block,
    simulation_window_deadline,
)


def test_pure_turn_expected_signs_and_magnitude():
    ccw = expected_pure_turn_wheel_omega(0.40, 0.42, 0.09)
    cw = expected_pure_turn_wheel_omega(-0.40, 0.42, 0.09)
    assert math.isclose(ccw["left"], -0.9333333333333333)
    assert math.isclose(ccw["right"], 0.9333333333333333)
    assert math.isclose(cw["left"], 0.9333333333333333)
    assert math.isclose(cw["right"], -0.9333333333333333)


def test_general_wheel_kinematics_handles_straight_motion():
    straight = expected_wheel_omega(0.20, 0.0, 0.42, 0.09)
    assert math.isclose(straight["left"], 2.2222222222222223)
    assert math.isclose(straight["right"], 2.2222222222222223)


def test_joint_state_block_extracts_timestamp_position_and_velocity():
    block = '''
header { stamp { sec: 12 nsec: 345000000 } }
joint {
  name: "wheel_left_joint"
  axis1 { position: -1.25 velocity: -0.933333 }
}
joint {
  name: "wheel_right_joint"
  axis1 { position: 2.50 velocity: 0.933333 }
}
'''
    parsed = parse_joint_state_block(block)
    assert parsed["stamp_s"] == 12.345
    assert parsed["joints"]["wheel_left_joint"] == {"position": -1.25, "velocity": -0.933333}
    assert parsed["joints"]["wheel_right_joint"] == {"position": 2.5, "velocity": 0.933333}


def test_simulation_window_deadline_is_independent_of_wall_rate():
    assert simulation_window_deadline(100.0, 0.25) == 100.25
    assert simulation_window_deadline(100.0, 4.0) == 104.0


def test_dynamic_pose_block_extracts_named_model_pose():
    block = '''
header { stamp { sec: 3 nsec: 500000000 } }
pose {
  name: "amr_robot"
  position { x: 0.12 y: -0.03 z: 0.001 }
  orientation { z: 0.5 w: 0.8660254038 }
}
'''
    parsed = parse_dynamic_pose_block(block, "amr_robot")
    assert parsed["stamp_s"] == 3.5
    assert parsed["x"] == 0.12
    assert parsed["y"] == -0.03
    assert parsed["z"] == 0.001
    assert parsed["yaw"] > 1.0


def test_dynamic_pose_json_line_extracts_named_model_pose():
    line = (
        '{"header":{"stamp":{"sec":"3","nsec":500000000}},'
        '"pose":[{"name":"amr_robot","position":{"x":0.12,"y":-0.03,"z":0.001},'
        '"orientation":{"z":0.5,"w":0.8660254038}}]}'
    )
    parsed = parse_dynamic_pose_json_line(line, "amr_robot")
    assert parsed["stamp_s"] == 3.5
    assert parsed["x"] == 0.12
    assert parsed["y"] == -0.03
    assert parsed["z"] == 0.001
    assert parsed["yaw"] > 1.0


if __name__ == "__main__":
    test_pure_turn_expected_signs_and_magnitude()
    test_general_wheel_kinematics_handles_straight_motion()
    test_joint_state_block_extracts_timestamp_position_and_velocity()
    test_simulation_window_deadline_is_independent_of_wall_rate()
    test_dynamic_pose_block_extracts_named_model_pose()
    test_dynamic_pose_json_line_extracts_named_model_pose()
    print("phase4k diagnostic tests passed")
