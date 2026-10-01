# Scan Invalid-Value Replay Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compare raw and existing-filtered `/scan` replay through the unchanged Jazzy `slam_toolbox` configuration and determine whether invalid LaserScan values materially contribute to map-to-odom corrections.

**Architecture:** Use the preserved remote rosbag as the sole sensor/time source. Run one raw replay and one filtered replay with the same SLAM launch and capture replay outputs into separate evidence directories; do not alter project code, SLAM parameters, Isaac Sim, or the baseline bag.

**Tech Stack:** ROS 2 Jazzy, rosbag2 SQLite, `amr_description/scan_filter_node.py`, `slam_toolbox`, Python/ROS message deserialization for offline metrics.

## Global Constraints

- Do not change any `slam_toolbox` parameter.
- Do not delete `/home/gspe-ai3/slam_investigation/bags/live_baseline_20260930_101706`.
- Use the same recorded `/scan`, `/odom`, `/tf`, `/tf_static`, `/clock`, and `/cmd_vel` data for both runs.
- Stop if the raw replay does not reproduce the baseline correction pattern sufficiently.
- Do not start a second experiment automatically.

### Task 1: Verify the existing filter

**Files:**
- Read: `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/scripts/scan_filter_node.py`
- Read: `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/CMakeLists.txt`

- [ ] Record exact handling of negative, NaN, infinite, below-minimum, and above-maximum ranges with file and line references.
- [ ] Verify the installed executable resolves to this source without editing it.

### Task 2: Run raw replay baseline

**Files:**
- Read: `/home/gspe-ai3/slam_investigation/bags/live_baseline_20260930_101706`
- Create evidence only under: `/home/gspe-ai3/slam_investigation/replay/`

- [ ] Launch only the existing `slam_launch.py` with the preserved `slam_cfg.yaml`.
- [ ] Replay the recorded sensor, odometry, TF, clock, and command topics without Isaac Sim.
- [ ] Capture `/map`, SLAM pose/TF output, SLAM logs, and replay timing.
- [ ] Compute yaw/translation correction metrics and compare the normal/skew/recovery/skew pattern.
- [ ] Stop if the raw replay is not sufficiently reproducible.

### Task 3: Run filtered replay

**Files:**
- Read: `/home/gspe-ai3/ros2_gprp_amr_ws/install/amr_description/lib/amr_description/scan_filter_node.py`
- Create evidence only under: `/home/gspe-ai3/slam_investigation/replay/filtered/`

- [ ] Insert the existing filter between replayed `/scan` and SLAM using only topic routing.
- [ ] Keep all non-scan replay topics, SLAM parameters, and playback timing identical.
- [ ] Capture the same outputs and compute the same metrics.

### Task 4: Compare and stop

- [ ] Produce the requested raw-versus-filtered table.
- [ ] Classify the result as supported contributor, no material effect, or inconclusive.
- [ ] Report that the baseline bag remains preserved and request approval before deleting it.
