# Simulation Corridor Safety and Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Isaac Sim navigation stack stop safely before corridor-wall contact, then add a validated strategy for reaching a safe turning area before reversing or rotating.

**Architecture:** The first phase is a simulation-only safety containment change: one final velocity path, an active Collision Monitor, no direct `/cmd_vel` publisher from the simulation behavior tree, and bounded recovery retries. The second phase is a separate maneuver design based on measured free space and explicit staging poses; it will not blindly reverse or spin in a narrow corridor.

**Tech Stack:** ROS 2 Jazzy, Nav2, MPPI controller, Smac Hybrid/Reeds-Shepp planner, BehaviorTree.CPP, Isaac Sim, YAML, `colcon`.

## Global Constraints

- Simulation only: modify `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/**` only unless a later approved plan says otherwise.
- Do not modify `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_bringup/**`.
- Do not modify the real-robot configuration, EKF, SLAM, Isaac LiDAR, map, footprint, or inflation values.
- Do not modify `robot_agent_node.py` or the Web UI for Phase 1.
- Do not start Isaac, Navigation, missions, rosbag recording, or publish `/cmd_vel` during implementation.
- Preserve the dirty worktree and all existing experiment bags.
- Create a timestamped backup before each configuration edit.
- No additional MPPI, planner, or critic tuning is part of this plan.
- A physical wall contact is a failed safety test even if Nav2 reports success or the costmap reports clearance.

## Current Evidence and Design Decisions

- The simulation configuration currently uses MPPI, `vx_min=-0.6`, `wz_max=0.4`, `PathAngleCritic.mode=2`, `PreferForwardCritic.enabled=true`, and `ObstaclesCritic.collision_margin_distance=0.10`.
- The chassis footprint in the simulation configuration matches the measured collision mesh bounds approximately: `0.783 x 0.582 m`. A gross footprint-size error is not currently proven.
- Collision Monitor is launched by the Nav2 launch path but its configured safety sources are disabled.
- `CorridorDetourWait` currently publishes directly to `/cmd_vel`, which can bypass the normal velocity-smoother/Collision-Monitor ownership path. The simulation behavior tree must stop using that direct command path before safety results are trusted.
- The current Behavior Tree retries/waits repeatedly and has no turning-bay, staging-pose, or bounded safe-abort behavior.
- The agent currently sends station poses; it does not decide whether to reverse, seek a turning area, or rotate in place.

## Phase 1: Simulation Safety Containment

### Task 1: Capture the exact pre-change state

**Files:**
- Read: `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/config/amr_cfg.yaml`
- Read: `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/behavior_trees/navigate_to_pose_wait_20s.xml`
- Read: `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/launch/amr_navigation_sim_launch.py`

**Steps:**

- [ ] Record `git status --short --branch` and do not reset or clean the worktree.
- [ ] Record the current values of `collision_monitor`, `FootprintApproach`, `scan`, and `depth` enable flags.
- [ ] Record the current `RecoveryNode` retry count and every `CorridorDetourWait` occurrence in the simulation BT.
- [ ] Record the current launch remappings for `/cmd_vel_nav`, `/cmd_vel_smoothed`, `/cmd_vel`, `/scan`, and `/scan_filtered`.
- [ ] Create a timestamped copy of `amr_cfg.yaml` before editing it.
- [ ] Create a timestamped copy of the simulation BT before editing it.

**Acceptance:** The exact pre-change values and backups are recorded; no process is started and no source file is changed except the backup copies.

### Task 2: Activate the existing simulation safety layer

**Files:**
- Modify: `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/config/amr_cfg.yaml`

**Steps:**

- [ ] Keep the existing Collision Monitor numeric settings unchanged.
- [ ] Enable only the already-defined simulation safety sources: `FootprintApproach`, `scan`, and `depth`, using the existing Jazzy configuration structure.
- [ ] Do not change `collision_margin_distance`, footprint, inflation, velocity limits, accelerations, controller critics, planner penalties, or sensor topics.
- [ ] Verify the resulting command ownership is intended to be:

```text
/cmd_vel_nav
  -> velocity_smoother
/cmd_vel_smoothed
  -> collision_monitor
/cmd_vel
```

**Acceptance:** YAML parses successfully and the diff contains only the approved Collision Monitor enable changes.

### Task 3: Remove the direct simulation `/cmd_vel` path

**Files:**
- Modify: `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/behavior_trees/navigate_to_pose_wait_20s.xml`
- Do not modify: `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/src/corridor_detour_nodes.cpp` in this phase.

**Steps:**

- [ ] Remove `CorridorDetourWait` from the simulation `ReactiveSequence`, so this simulation BT no longer loads the node that publishes directly to `/cmd_vel`.
- [ ] Keep `FollowPath` as the only controller action in that sequence.
- [ ] Leave the real-robot BT and the C++ plugin source unchanged.
- [ ] Confirm the simulation BT still selects `GridBased` and `FollowPath` and does not add a new recovery command.

**Acceptance:** Static search of the simulation BT shows no `CorridorDetourWait`; no simulation behavior-tree node publishes a direct `/cmd_vel`; the real-robot files are byte-for-byte untouched.

### Task 4: Bound unsafe retry behavior

**Files:**
- Modify: `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/behavior_trees/navigate_to_pose_wait_20s.xml`

**Steps:**

- [ ] Change only the simulation `RecoveryNode` retry count from the current unbounded-feeling value of `100` to `1`.
- [ ] Keep the existing planner/controller selection and goal semantics unchanged.
- [ ] Do not add blind `BackUp`, `Spin`, or `DriveOnHeading` recovery actions.
- [ ] Treat an unsafe corridor state as a bounded navigation failure until a dedicated maneuver is implemented.

**Acceptance:** A blocked simulation goal cannot produce an indefinite `Start occupied -> wait -> replan` loop; the BT XML remains valid.

### Task 5: Static and build verification

**Files:**
- Build: `amr_description`

**Steps:**

- [ ] Parse the edited YAML with PyYAML and print the changed keys.
- [ ] Validate the BT XML with the available XML parser.
- [ ] Run the simulation launch dry-run or `ros2 launch ... --show-args` without starting the launch.
- [ ] Build only `amr_description` with the workspace's existing build command and `--symlink-install`.
- [ ] Confirm no files under `amr_bringup` changed.
- [ ] Confirm the installed simulation YAML and BT point to the intended source files/symlinks.

**Acceptance:** YAML/XML/build checks pass, the diff is limited to simulation safety changes, and no ROS process is launched by the verification.

### Task 6: Controlled safety test

**Runtime procedure:**

- [ ] User starts Isaac and Navigation through the normal Web UI workflow.
- [ ] Verify exactly one Navigation stack and exactly one Collision Monitor.
- [ ] Verify `/cmd_vel_nav`, `/cmd_vel_smoothed`, and `/cmd_vel` publisher/subscriber ownership.
- [ ] Verify the final `/cmd_vel` publisher is Collision Monitor and no custom BT node publishes it.
- [ ] Verify the simulation sensor chain and TF chain before sending a goal.
- [ ] Start a new timestamped evidence bag only after runtime verification.
- [ ] User sends the same narrow-corridor goal once.
- [ ] If contact or unsafe clearance is observed, cancel immediately and preserve the bag.

**Pass criteria:**

- No physical wall contact.
- No direct custom publisher on `/cmd_vel`.
- Collision Monitor reduces or stops the command before the robot reaches the wall.
- No repeated recovery loop after the first unsafe condition.

**Important:** A safe stop with navigation failure is a Phase 1 pass. It is not yet a successful corridor-navigation result.

## Phase 2: Safe Corridor Maneuver Design

This phase must not begin until Phase 1 passes. It is a separate behavioral change and requires a new approval.

### Task 7: Measure the turning geometry

**Files:**
- Read: simulation map, costmaps, footprint, URDF collision mesh, and station data.
- Create only an analysis report; do not edit navigation configuration.

**Steps:**

- [ ] Measure the narrow corridor width from the map/costmap.
- [ ] Compute the robot footprint clearance in forward and reverse directions.
- [ ] Check whether the robot can rotate within the corridor using the actual footprint and required turning radius.
- [ ] Identify the nearest areas that can contain the swept footprint during a turn.
- [ ] Mark candidate staging poses with position and yaw; do not yet send them to Nav2.

**Acceptance:** Every proposed turning pose has measured clearance for the complete swept footprint, not only the robot center point.

### Task 8: Choose the first maneuver implementation

Use this priority order:

1. Explicit staging waypoint in the simulation mission route.
2. If no fixed waypoint is suitable, a simulation-only maneuver node that evaluates candidate poses before commanding movement.
3. Only after those are proven, consider dynamic “find an open area” behavior.

The first maneuver implementation must obey:

- Never reverse unless rear clearance is verified.
- Never rotate in place unless the complete swept footprint is clear.
- Abort and hold if no candidate is safe.
- Do not infer safety from goal yaw alone.
- Do not issue direct `/cmd_vel`; all motion must pass through the standard Nav2 command/safety chain.

### Task 9: Validate the maneuver separately

**Acceptance metrics:**

- Zero physical wall contact.
- Zero lethal footprint intersection.
- Minimum measured clearance stays above the agreed safety threshold.
- No uncontrolled angular-velocity saturation.
- No repeated `Start occupied` loop.
- The robot either reaches the staging pose and turns, or stops with a clear safe-abort result.

Compare the maneuver against the preserved baseline and Phase 1 bag. Do not combine this test with MPPI critic tuning.

## Files Expected to Change

For Phase 1 only:

- `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/config/amr_cfg.yaml`
- `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_description/behavior_trees/navigate_to_pose_wait_20s.xml`

Expected not to change:

- `/home/gspe-ai3/ros2_gprp_amr_ws/src/amr_bringup/**`
- `/home/gspe-ai3/amr_agent/**`
- Isaac configuration and stage
- EKF, SLAM, map, footprint dimensions, inflation, and controller/planner tuning

`amr_navigation_sim_launch.py` will be inspected and changed only if a launch-level remap is proven to violate the command chain; no launch edit is currently required by the audit.

## Self-Review

- The plan separates safety containment from corridor maneuver behavior, so a tuning change cannot be mistaken for a safety fix.
- It preserves the real-robot path and the current agent/Web UI ownership model.
- It does not assume that a costmap result proves absence of physical contact.
- It explicitly tests command ownership, because the direct `/cmd_vel` publisher is otherwise able to invalidate Collision Monitor conclusions.
- It does not add blind reverse or spin recovery.

