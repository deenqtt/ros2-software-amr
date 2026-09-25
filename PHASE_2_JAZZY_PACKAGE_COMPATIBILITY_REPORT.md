# Phase 2 — ROS 2 Jazzy Package Compatibility Report

Tanggal audit: 2026-09-17  
Scope: package manifest, custom interface, dan custom-node compatibility pada ROS 2 Jazzy/Noble.  
Batasan: Gazebo Classic → Harmonic belum dikerjakan.

## 1. Executive summary

Phase 2 membuat bagian non-Gazebo workspace lebih akurat terhadap dependency
aktual dan dapat dibangun pada Jazzy. Kontrak ROS simulator tetap frozen.

Hasil penting:

- `custom_interfaces`, `amr_docking`, dan `amr_navigation` lulus clean Jazzy
  build gate;
- seluruh interface yang dipakai aplikasi, termasuk `RobotMode`, berhasil
  digenerate dan di-introspect;
- lima custom Python node berhasil di-import dan dikonstruksi pada Jazzy;
- mismatch `StationConfig` pada docking manager diperbaiki tanpa mengubah `.srv`;
- `opennav_docking_msgs` terbukti bukan dependency aktif project dan tidak
  tersedia sebagai standalone apt/rosdep package pada image Jazzy yang diuji;
- full workspace masih terhalang hanya oleh `gazebo_ros_pkgs`, yang sengaja
  dipertahankan sebagai boundary migrasi Gazebo;
- `amr_simulation` dan `amr_bringup` tidak dimasukkan ke eligible build gate:
  yang pertama masih Classic-coupled, yang kedua transitively bergantung padanya.

Status akhir Phase 2: **PASS** untuk target non-Gazebo; **DEFERRED** untuk
runtime Gazebo dan bringup yang bergantung pada runtime tersebut.

## 2. Pre-Phase-2 Git state

Safety check dijalankan sebelum perubahan:

```text
branch: main
HEAD: 3ddde28b668d646fed8f9e39188a9f1153e74a28
tracking: main...origin/main
```

Tracked changes Phase 0/1 masih uncommitted. File untracked yang sudah ada
sebelum Phase 2 adalah `ROS2_JAZZY_MIGRATION_RESEARCH_AND_PLAN.md`; file itu
dipertahankan dan tidak diubah. Tidak dilakukan reset, checkout, clean, stash,
commit, push, atau branch switch.

## 3. Package inventory

| Package | Build type | Jazzy status | Gazebo coupled | Phase 2 build eligible | Issues / disposition |
| --- | --- | --- | --- | --- | --- |
| `custom_interfaces` | `ament_cmake` + `rosidl` | PASS | No | Yes | `RobotMode.srv` sebelumnya belum masuk generator; diperbaiki |
| `amr_docking` | `ament_cmake` + installed Python nodes | PASS | No direct coupling | Yes | Manifest dilengkapi; stale OpenNav deps dihapus; `StationConfig` dan OpenCV fixes |
| `amr_navigation` | `ament_cmake` + installed Python nodes | PASS | No direct coupling; Nav2 runtime pending | Yes | Manifest dilengkapi terhadap imports dan launch API |
| `amr_simulation` | `ament_cmake` + launch/assets/Python | DEFERRED | Yes | No | `gazebo_ros`, `gazebo_ros_pkgs`, Classic launch/plugins/world/URDF |
| `amr_bringup` | `ament_cmake` + orchestration launch | DEFERRED | Indirect | No | Depends on `amr_simulation`; full bringup remains Gazebo-coupled |

Tidak ditemukan package `ament_python`, `setup.py`, atau `setup.cfg`. Python
nodes dipasang melalui `install(PROGRAMS ...)` pada CMake dan executable bits
yang diperlukan sudah dipulihkan.

## 4. Files changed

Phase 2 mengubah atau menambahkan:

- `ros2_ws/src/amr_bringup/package.xml`
- `ros2_ws/src/amr_docking/package.xml`
- `ros2_ws/src/amr_docking/scripts/docking_manager_node.py`
- `ros2_ws/src/amr_docking/scripts/aruco_detector_node.py`
- `ros2_ws/src/amr_navigation/package.xml`
- `ros2_ws/src/amr_simulation/package.xml`
- `ros2_ws/src/custom_interfaces/CMakeLists.txt`
- executable mode custom Python scripts yang dipasang CMake;
- `docs/JAZZY_DEPENDENCY_STATUS.md`
- `docs/ROS_INTERFACE_CONTRACT.md`
- file ini.

Perubahan Phase 0/1 tetap ada pada Docker dan helper scripts. Tidak ada source
Web UI atau backend yang diubah.

## 5. Manifest dan build metadata changes

Manifest diperbaiki secara minimum berdasarkan import/launch aktual:

- `amr_bringup`: `launch`, `launch_ros`, dan `amr_docking` ditambahkan;
- `amr_docking`: `geometry_msgs`, `lifecycle_msgs`, dan `nav_msgs` ditambahkan;
  dependency OpenNav dihapus karena tidak dipakai node/launch aktif;
- `amr_navigation`: `ament_index_python`, `launch`, `launch_ros`, `nav2_msgs`,
  `action_msgs`, `geometry_msgs`, `nav_msgs`, `rclpy`, `std_msgs`, `std_srvs`,
  dan `custom_interfaces` ditambahkan;
- `amr_simulation`: dependency launch, runtime battery, robot description,
  Nav2 map/lifecycle, dan xacro ditambahkan;
- `gazebo_ros` dan `gazebo_ros_pkgs` tetap ada pada `amr_simulation` dengan
  komentar boundary, karena menghapusnya akan menyamarkan pekerjaan porting;
- `custom_interfaces/CMakeLists.txt` sekarang menghasilkan `RobotMode.srv`.

Tidak ada perubahan pada nama field, type, topic, service, action, namespace,
atau TF frame aplikasi.

## 6. custom_interfaces validation

Clean Jazzy build menghasilkan:

```text
Starting >>> custom_interfaces
Finished <<< custom_interfaces
Summary: 3 packages finished
```

Pada build gate yang sama, seluruh interface berikut berhasil dijalankan dengan
`ros2 interface show`:

- `custom_interfaces/msg/RobotStatus`
- `custom_interfaces/srv/DockCommand`
- `custom_interfaces/srv/StationConfig`
- `custom_interfaces/srv/RobotMode`
- `custom_interfaces/action/MissionPlan`

Status: **PASS**.

Catatan: temuan `RobotMode.srv` adalah bug build metadata yang nyata. File
definition sudah ada dan UI sudah menggunakannya, tetapi generator sebelumnya
tidak mendaftarkannya. Fix hanya menambahkan file ke daftar generator.

## 7. StationConfig mismatch investigation

Evidence yang dibandingkan:

- committed definition: `station_id`, `type`, `x_pose`, `y_pose`, `yaw_pose`,
  `action`;
- `mission_manager_node.py`: sudah memakai field committed;
- `web-ui/src/composables/useROS.js`: mengirim `station_id`, `type`, `action`,
  `x_pose`, `y_pose`, `yaw_pose`;
- `docking_manager_node.py` lama: memakai field yang tidak ada, yaitu `id`,
  `name`, `x_approach`, `y_approach`, dan `yaw_approach`.

Kesimpulan: `.srv` committed adalah contract authority; docking manager adalah
consumer yang stale/wrong. Fix minimal:

- gunakan `request.station_id` dan field pose committed;
- simpan target pose yang sama;
- turunkan approach pose internal 0,5 m di belakang target berdasarkan
  `yaw_pose`, karena contract frozen tidak memiliki field approach;
- validasi action hanya `0=delete` atau `1=save`;
- response tetap service `string result` yang sama.

Tidak ada redesign docking API dan tidak ada perubahan Web UI.

Status mismatch: **PASS** untuk compatibility disposition dan smoke test; full
docking behavior tetap **DEFERRED** karena membutuhkan Nav2/Gazebo runtime.

## 8. `opennav_docking_msgs` investigation

Repository source dan runtime project tidak mengimpor `opennav_docking_msgs`,
tidak meluncurkan OpenNav docking server, dan docking aktif memakai
`custom_interfaces` plus `NavigateToPose`. File
`amr_docking/config/docking_params.yaml` masih dipertahankan sebagai konfigurasi
historis/future option, tetapi tidak direferensikan oleh launch aktif.

Bukti Jazzy/Noble:

- `apt-cache search "ros-jazzy-.*docking"` menemukan `ros-jazzy-opennav-docking`,
  `-bt`, dan `-core`, tetapi tidak menemukan standalone
  `ros-jazzy-opennav-docking-msgs`;
- `/opt/ros/jazzy/share/opennav_docking_msgs` tidak ada;
- `nav2_msgs/action/DockRobot` tersedia dan berhasil di-introspect;
- upstream Open Navigation README menjelaskan `opennav_docking_msgs` sebagai
  package interface terpisah pada repository dan mencatat capability tersebut
  telah dipindahkan ke Nav2 sejak Juni 2024;
- official installed `opennav_docking/package.xml` di image Jazzy tidak
  mendeklarasikan `opennav_docking_msgs`.

Disposition: deklarasi `opennav_docking_msgs` pada project ini adalah stale dan
tidak dibutuhkan oleh architecture custom docking saat ini. Deklarasi
`opennav_docking` juga dihapus dari `amr_docking/package.xml` karena package
tersebut tidak dipakai oleh node/launch aktif; opsi OpenNav tetap tercatat untuk
keputusan arsitektur fase berikutnya.

Status: **PASS** untuk investigation; OpenNav migration **DEFERRED**.

Referensi: [Open Navigation docking README](https://github.com/open-navigation/opennav_docking/blob/main/README.md)
dan [Nav2 migration documentation](https://docs.nav2.org/rolling/configuration_and_development/migration_guides/iron/Iron/).

## 9. Custom Python ROS node compatibility

Node yang diaudit:

- `battery_sim_node.py`;
- `docking_manager_node.py`;
- `aruco_detector_node.py`;
- `keepout_mask_server.py`;
- `mission_manager_node.py`.

Audit mencakup `rclpy`, publisher/subscriber, service/client, action
server/client, callback group, executor, parameter API, QoS, TF/action message
construction, shutdown path, dan imports aktual.

Perubahan berbasis evidence:

- `docking_manager_node.py`: StationConfig field mismatch diperbaiki;
- `aruco_detector_node.py`: image OpenCV Jazzy adalah 4.6.0; API yang tersedia
  tidak memiliki `cv2.aruco.drawAxis`, sehingga dipakai
  `cv2.drawFrameAxes`;
- executable bits script yang dipasang CMake dipastikan aktif.

Node-level test meng-import dan mengonstruksi kelima node dalam satu Jazzy
context. Semua PASS. Test juga memanggil callback StationConfig dan
memverifikasi approach pose hasil derivasi.

Runtime yang membutuhkan simulator/Gazebo, sensor stream, atau Nav2 server
tidak diklaim berhasil dan tetap **DEFERRED**.

## 10. Known baseline inconsistencies

Sesuai instruksi, tidak ada functionality spekulatif yang ditambahkan:

| Finding | Disposition | Reason |
| --- | --- | --- |
| UI memanggil `/robot_mode`, provider tidak ditemukan di bringup | DEFERRED | intent orchestrator belum jelas; interface tetap ada |
| UI publish `/amr/mission_payload`, subscriber tidak ditemukan | DOCUMENT ONLY | tidak mengubah contract atau membuat subscriber fiktif |
| komentar menyebut Foxglove, runtime memakai rosbridge | DOCUMENT ONLY | dokumentasi mismatch, tidak berdampak pada Phase 2 build |

`docs/ROS_INTERFACE_CONTRACT.md` diperbarui hanya dengan implementation notes
terverifikasi; bagian real-robot mapping tetap `TBD`.

## 11. Gazebo boundary / packages deferred

`amr_simulation` tetap memiliki:

- `gazebo_ros` dan `gazebo_ros_pkgs`;
- `gazebo_ros/launch/gazebo.launch.py`;
- `gazebo_ros/spawn_entity.py`;
- Classic plugin libraries pada URDF;
- Classic `.world` dan model integration.

Tidak ada `.world` conversion, SDF conversion, plugin replacement, sensor
bridge, atau `ros_gz_bridge` mapping pada Phase 2.

`amr_bringup` juga deferred dari eligible gate karena launch chain-nya langsung
menjalankan `amr_simulation` dan custom simulation nodes. Ini adalah boundary
transitif, bukan alasan untuk mengubah application contract.

## 12. Full-workspace rosdep result

Command:

```bash
rosdep install --from-paths src --ignore-src -y --rosdistro jazzy
```

Result:

```text
ERROR: the following packages/stacks could not have their rosdep keys resolved
to system dependencies:
amr_simulation: Cannot locate rosdep definition for [gazebo_ros_pkgs]
```

Status: **BLOCKED**, tetapi blocker tunggal ini adalah dependency Classic yang
memang dipertahankan untuk fase Gazebo. `opennav_docking_msgs` tidak lagi
menjadi blocker setelah disposition stale/unneeded terbukti.

## 13. Phase-2-targeted rosdep result

Command equivalent for the complete source graph while explicitly excluding
only the known Gazebo boundary:

```bash
rosdep install --from-paths src --ignore-src \
  --skip-keys "gazebo_ros gazebo_ros_pkgs" \
  -y --rosdistro jazzy
```

Result:

```text
#All required rosdeps installed successfully
```

Status: **PASS**. This must not be confused with full-workspace resolution;
the two Classic keys remain intentionally skipped.

## 14. Colcon build result

Final clean eligible command:

```bash
colcon build --symlink-install \
  --packages-select custom_interfaces amr_docking amr_navigation
```

Result:

```text
Starting >>> custom_interfaces
Finished <<< custom_interfaces
Starting >>> amr_docking
Finished <<< amr_docking
Starting >>> amr_navigation
Finished <<< amr_navigation
Summary: 3 packages finished
```

Packages built: `custom_interfaces`, `amr_docking`, `amr_navigation`. Status:
**PASS**.

A broader selection including `amr_bringup` was also attempted. Three packages
finished, then `amr_bringup` failed because its selected build graph lacked the
installed package metadata for deferred `amr_simulation`:

```text
Failed to find:
/ros2_ws/install/amr_simulation/share/amr_simulation/package.sh
```

This confirms the transitive boundary and is recorded as **DEFERRED**, not
hidden by building a fake or incomplete simulation package.

## 15. Packages skipped and exact reasons

| Package | Status | Exact reason |
| --- | --- | --- |
| `amr_simulation` | DEFERRED | Current package declares unresolved `gazebo_ros_pkgs` and contains Classic launch/plugins/world/URDF |
| `amr_bringup` | DEFERRED | Bringup directly includes `amr_simulation`; selected build cannot resolve its package environment until that boundary is built/migrated |

No eligible package was skipped. The build was not run with a blanket ignore
that could conceal an eligible package failure.

## 16. Node/import/introspection smoke tests

| Test | Status | Evidence |
| --- | --- | --- |
| Python source and launch files compile in memory | PASS | all `*.py` under source compiled without writing generated files |
| custom interface introspection | PASS | five required interfaces shown by `ros2 interface show` |
| installed executable discovery | PASS | docking and navigation node executables listed by `ros2 pkg executables` |
| five node imports and constructors | PASS | battery, ArUco, docking, keepout, mission |
| StationConfig callback compatibility | PASS | committed fields accepted; derived approach verified |
| launch description generation | PASS | bringup, navigation, simulation, and SLAM descriptions generated |
| full node runtime with Gazebo/Nav2 | DEFERRED | requires later simulator integration |

## 17. ROS Interface Contract impact

The contract remains frozen. No application-facing topic, message type, service,
service type, action, action type, namespace, or TF name was changed.

Verified additions to the contract documentation:

- UI sends the committed StationConfig fields;
- mission manager and docking manager now agree on those fields;
- `RobotMode.srv` is generated and introspectable;
- real robot interface mapping remains `TBD`.

The contract file itself is unchanged in meaning; only verified implementation
notes were added.

## 18. Dependency status updates

`docs/JAZZY_DEPENDENCY_STATUS.md` now records:

- `custom_interfaces`: A / directly available and validated;
- `opennav_docking`: available as a future option but not an active dependency;
- `opennav_docking_msgs`: D/E for this project—stale declaration and no
  standalone Jazzy apt/rosdep package; `nav2_msgs/action/DockRobot` exists;
- full rosdep failure reduced to `gazebo_ros_pkgs` only;
- targeted rosdep and eligible colcon evidence;
- OpenCV 4.6 API compatibility note;
- Gazebo boundary and package eligibility.

## 19. Failures and blockers

| Item | Status | Explanation |
| --- | --- | --- |
| full workspace rosdep | BLOCKED | retained Gazebo Classic `gazebo_ros_pkgs` |
| full workspace colcon | DEFERRED | not legitimate until Gazebo package boundary is migrated |
| `amr_bringup` in isolated eligible selection | DEFERRED | requires deferred `amr_simulation` package environment |
| Nav2/SLAM behavior | DEFERRED | no simulator clock/sensor/TF runtime in this phase |
| physical robot compatibility | NOT TESTED | interface documentation remains intentionally `TBD` |

## 20. Risks discovered

- `amr_simulation` must be ported before full bringup can be a meaningful Jazzy
  runtime test;
- the derived 0.5 m approach pose is a simulator-side compatibility fallback,
  not a real robot docking specification;
- Nav2 YAML/plugin behavior and lifecycle startup still require a later runtime
  gate;
- `/robot_mode` provider and `/amr/mission_payload` subscriber remain unknown;
- OpenNav adoption would change docking architecture and must be separately
  approved; it was not inferred from package availability.

## 21. `git diff --stat`

Tracked files at final Phase 2 audit:

```text
 docker-compose.yml                                 |  24 +++-
 docker/Dockerfile                                  |  69 ++++++----
 docker/entrypoint.sh                               |  10 +-
 ros2_ws/src/amr_bringup/package.xml                |   3 +
 ros2_ws/src/amr_docking/package.xml                |   7 +-
 .../src/amr_docking/scripts/aruco_detector_node.py |   4 +-
 .../amr_docking/scripts/docking_manager_node.py    |  28 ++--
 ros2_ws/src/amr_navigation/package.xml             |  11 ++
 .../amr_navigation/scripts/mission_manager_node.py |   0
 ros2_ws/src/amr_simulation/package.xml             |   8 ++
 .../src/amr_simulation/scripts/battery_sim_node.py |   0
 ros2_ws/src/custom_interfaces/CMakeLists.txt       |   1 +
 scripts/build_ws.sh                                |  12 +-
 scripts/docker_run.sh                              |  26 ++--
 scripts/install_ros2.sh                            | 142 +++------------------
 15 files changed, 155 insertions(+), 190 deletions(-)
```

`git diff --stat` tidak menghitung dokumen baru yang masih untracked. Tidak ada
file yang di-stage atau di-commit.

## 22. Exact validation matrix

| Validation | Status | Result |
| --- | --- | --- |
| pre-write Git safety check | PASS | branch/HEAD/status/diff/untracked recorded |
| all ROS package inventory | PASS | five packages audited |
| package manifest audit | PASS | imports, launch files, build/install metadata compared |
| custom interfaces build | PASS | generated on Jazzy |
| custom interface introspection | PASS | RobotStatus, four services/action |
| StationConfig disposition | PASS | stale consumer corrected without contract change |
| OpenNav messages investigation | PASS | stale current declaration; standalone package absent; Nav2 action verified |
| custom Python audit | PASS | five node constructor/import smoke tests |
| full rosdep | BLOCKED | `gazebo_ros_pkgs` only |
| Phase-2-targeted rosdep | PASS | all required rosdeps installed with known Gazebo keys skipped |
| eligible colcon build | PASS | three packages finished |
| deferred package isolation | PASS | simulation and transitive bringup boundary explicit |
| full Gazebo simulation | NOT TESTED | prohibited until Phase 3 |
| Web UI/backend redesign | NOT TESTED | prohibited and no source changed |
| real robot interface | NOT TESTED | remains `TBD` by rule |

## 23. Recommendation for Phase 3

Proceed only after approval with the separate Gazebo migration plan:

1. map current world/model/URDF/plugin behavior to Gazebo Sim Harmonic;
2. replace Classic launch/spawn/plugin paths with validated `ros_gz` components;
3. add explicit bridge mappings while preserving the frozen ROS application
   contract;
4. run clock, TF, sensor, `cmd_vel`, Nav2, SLAM, rosbridge, and Web UI runtime
   gates;
5. decide separately whether custom docking remains or OpenNav/Nav2 docking is
   adopted.

Do not infer physical robot interfaces during that work. Stop here until Phase 3
is explicitly approved.
