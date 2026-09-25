# Archive

Completed work, kept for engineering value. **Nothing here is current reference documentation** — for that, see [../README.md](../README.md).

Do not delete these without reading them. Several files are the only written record of *why* an interface, a physics parameter, or a launch sequence is shaped the way it is.

---

## `phases/` — phase completion reports

16 reports covering the ROS 2 Humble → Jazzy migration and the Gazebo Harmonic robot runtime work, September 2026.

| Range | Subject | Why it still matters |
|---|---|---|
| `PHASE_0_1` … `PHASE_3` | Jazzy migration, package compatibility, Gazebo Harmonic foundation | Records which packages were replaced and why |
| `PHASE_4`, `PHASE_4G`–`PHASE_4P` | Café AMR runtime, then the diff-drive slip investigation and motion calibration | **The current physics and motion parameters came from this sequence.** `4I` isolates the diff-drive root cause; `4K`–`4P` derive the slip response curve and final calibration |
| `PHASE_5A`, `PHASE_5B` | SLAM readiness audit and mapping acceptance | Records the accepted SLAM runtime behaviour |

## `plans/` — implementation plans

14 plans, one per phase, written before the corresponding report. Useful for reading intent against outcome.

## `designs/` — design documents

`2026-09-17-cafe-amr-physical-design.md` — the physical robot design the simulation model is based on.

## `investigations/` — closed investigations

| Document | Subject |
|---|---|
| `VELOCITY_POSE_DRIFT_ROOT_CAUSE_INVESTIGATION.md` | Velocity/pose drift root cause |
| `ODOMETRY_IMU_EKF_MAPPING_DIAGNOSTIC.md` | Odometry / IMU / EKF behaviour during mapping |
| `WEB_UI_STARTUP_PLAYWRIGHT_UX_AUDIT.md` | Browser-observed web UI startup sequence (2026-09-18). Superseded in scope by [`../WEB_UI_REDESIGN_AUDIT.md`](../WEB_UI_REDESIGN_AUDIT.md), but its runtime observations are still the only browser-verified record |

## `notes/` — working notes, not yet consolidated

Mixed Indonesian/English notes and `.txt` files from earlier development. **Pending review** — some content is still accurate and belongs in `docs/ROS_INTERFACE_CONTRACT.md`; the rest is superseded.

| File | Status |
|---|---|
| `docking_changes.md` | Review — extract anything still true into the ROS interface contract |
| `real_robot_docking_fix.md` | Review — same |
| `robot_status_analysis.md` | Review — relevant to the duplicate `/station_config` service conflict |
| `keepout_integration.txt` | Review — keepout ROS integration detail |
| `keepout_koordinasi_tim_robot.txt` | Team coordination note |
| `PROGRESS_WEBUI.txt` | Superseded by `WEB_UI_REDESIGN_AUDIT.md` |
| `LAPORAN_PROGRESS.md` | Superseded |
| `perubahan.md` | 126 bytes; verify then delete |

## `ROS2_JAZZY_MIGRATION_RESEARCH_AND_PLAN.md`

69 KB of research behind the Jazzy migration. The migration is complete; the research remains the reference for why each decision was made.

---

## Related: `../evidence/`

Raw captures (logs, JSON, resource snapshots) backing the Phase 4/5 investigations — roughly 86 MB across ~715 files, tracked in git. The phase reports above are the readable conclusions; `evidence/` is the underlying data.

Because it dominates clone size, a policy decision is pending: keep as-is, move to Git LFS, or keep per-phase conclusions in-repo and archive the raw captures externally. Until that is decided, leave it alone.

Note that `evidence/phase4o/baseline/repository-state.txt` and similar snapshots record file paths as they were **before** this reorganisation. That is expected — they are point-in-time records and must not be edited.
