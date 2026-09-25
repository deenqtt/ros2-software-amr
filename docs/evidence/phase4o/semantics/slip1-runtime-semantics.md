# Phase 4O `slip1` Runtime Semantics

## Local repository/runtime evidence

- Local `/opt/ros/jazzy` headers/share tree did not contain searchable prose
  documentation for `slip1`.
- `ros2_ws/src/amr_simulation/worlds/amr_world.sdf` uses
  `<physics name="1ms" type="ignored">`, `max_step_size=0.001`, and the
  native `gz-sim-physics-system`.
- A disposable Gazebo Sim 8.15.0 runtime was started with `-v 4`. Its log
  records:

  ```text
  Loaded [gz::physics::dartsim::Plugin]
  .../gz-physics-7/engine-plugins/libgz-physics-dartsim-plugin.so
  ```

  Evidence: `runtime-engine.log` in this directory.

## Official semantics consulted

The official SDFormat collision specification defines ODE `slip1` as
force-dependent slip in the first friction-pyramid direction, equivalent to
the inverse of a viscous damping coefficient, with units `m/s/N`; it states
that `slip1=0` is infinitely viscous. It defines `slip2` identically for the
second direction:

- https://sdformat.org/spec/1.12/collision/
- https://gazebosim.org/api/sdformat/15/classsdf_1_1SDF__VERSION__NAMESPACE_1_1ODE.html

The Gazebo Sim wheel-slip API describes the same force-dependent-slip units
and distinguishes them from a unitless slip-compliance ratio:

- https://gazebosim.org/api/sim/7/WheelSlip_8hh.html

Gazebo uses DART as the default physics engine, and the disposable runtime log
confirmed the DART plugin for this actual run:

- https://github.com/gazebosim/gz-sim/blob/main/tutorials/physics.md

## Interpretation boundaries

- In this runtime, `slip1=0` means no force-dependent velocity compliance in
  the first friction direction; it does **not** mean a real rubber wheel has
  literally zero physical slip.
- `slip1=0.035` is a simulator compliance parameter, not a measured tire
  coefficient. Its units are `m/s/N`.
- The repository contains no real-robot wheel/contact calibration data that
  justifies any nonzero value.
- Because the world leaves engine type selection as `ignored`, and the actual
  engine is DART, this report does not describe the result as Gazebo Classic
  ODE behavior. The observed curve is the behavior of the current Gazebo Sim
  8.15.0 + DART runtime consuming the SDF friction fields.
