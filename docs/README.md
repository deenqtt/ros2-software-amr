# Documentation index

Documentation for the AMR (Autonomous Mobile Robot) stack: ROS 2 Jazzy + Gazebo Harmonic simulation, a FastAPI backend, and a Vue 3 web control interface.

Start at the [root README](../README.md) for setup and quick start.

---

## Current reference

Documents describing how the system works today. Keep these updated.

| Document | Covers |
|---|---|
| [ROS_INTERFACE_CONTRACT.md](ROS_INTERFACE_CONTRACT.md) | Topics, services, actions and message types between the web UI and the robot |
| [WEB_UI_BACKEND_END_TO_END_ARCHITECTURE.md](WEB_UI_BACKEND_END_TO_END_ARCHITECTURE.md) | Frontend/backend/ROS architecture and data flows |
| [WEB_UI_REDESIGN_AUDIT.md](WEB_UI_REDESIGN_AUDIT.md) | Audit of the web UI and backend, multi-robot analysis, technology evaluation, redesign roadmap |
| [JAZZY_DEPENDENCY_STATUS.md](JAZZY_DEPENDENCY_STATUS.md) | ROS 2 Jazzy package availability and compatibility |
| [SHARED_MAP_STORAGE_NFS.md](SHARED_MAP_STORAGE_NFS.md) | Shared map storage over NFS |

## Runbooks

Operational command references.

| Document | Covers |
|---|---|
| [runbooks/AMR_SIMULATION_COMMANDS.md](runbooks/AMR_SIMULATION_COMMANDS.md) | Simulation launch and runtime commands. **Referenced by `scripts/docker_run.sh` — do not move.** |

## Decisions

[decisions/](decisions/) — architecture decision records. One file per decision, numbered, newest last.

## History

[history/](history/) — completed phase reports, superseded plans, and closed investigations. Preserved for engineering value, not current reference. See [history/README.md](history/README.md).

## Evidence

[evidence/](evidence/) — raw runtime captures (logs, JSON, resource snapshots) produced by the Phase 4/5 investigations. Large; see [history/README.md](history/README.md) for context.

---

## Where documentation belongs

| Kind of document | Location |
|---|---|
| How the system works now | `docs/` |
| An operational command sequence | `docs/runbooks/` |
| Why an architectural choice was made | `docs/decisions/` |
| A completed phase, plan or closed investigation | `docs/history/` |
| Raw data backing an investigation | `docs/evidence/<phase>/` |
| A ROS package's own interface reference | that package's directory, e.g. `ros2_ws/src/custom_interfaces/README.md` |

Only `README.md` lives at the repository root.
