# Phase 0/1 — ROS 2 Jazzy Foundation Implementation Report

Tanggal: 2026-09-17  
Repository: `ros2-software-amr`  
Scope: baseline/safety (Phase 0) dan Docker foundation ROS 2 Jazzy + Ubuntu 24.04 Noble (Phase 1).

## 1. Scope dan keputusan

Implementasi ini mengikuti rencana migrasi yang telah disetujui. Perubahan dibatasi pada:

- baseline interface dan dependency contract;
- Docker image/entrypoint/Compose untuk Jazzy/Noble;
- helper script agar memakai Docker-first Jazzy;
- verifikasi reproducible dan dokumentasi blocker.

Tidak dilakukan pada fase ini:

- konversi Gazebo Classic ke Gazebo Sim Harmonic;
- perubahan URDF, world, SDF, sensor, plugin, atau bridge simulasi;
- migrasi docking custom ke OpenNav Docking;
- migrasi Nav2/SLAM;
- perubahan source Web UI, backend, atau arsitektur docking.

Container default sengaja menjalankan foundation smoke container (`FOUNDATION_ONLY=true`). Ini membuat image dan environment dapat diverifikasi tanpa memberi kesan bahwa simulasi lama sudah kompatibel dengan Jazzy.

## 2. Baseline Git

Sebelum perubahan:

- branch aktif: `main`;
- HEAD: `3ddde28` (`first commit`);
- branch tracking: `main...origin/main`;
- tracked worktree bersih;
- `ROS2_JAZZY_MIGRATION_RESEARCH_AND_PLAN.md` sudah merupakan untracked file sebelum implementasi dan tidak diubah oleh pekerjaan ini.

Sesudah perubahan, tidak ada commit, push, reset, atau perubahan branch.

## 3. File yang berubah

Modified:

- `docker/Dockerfile`
- `docker/entrypoint.sh`
- `docker-compose.yml`
- `scripts/build_ws.sh`
- `scripts/docker_run.sh`
- `scripts/install_ros2.sh`

Added:

- `docs/ROS_INTERFACE_CONTRACT.md`
- `docs/JAZZY_DEPENDENCY_STATUS.md`
- file ini: `PHASE_0_1_JAZZY_IMPLEMENTATION_REPORT.md`

Preserved and not modified:

- `ROS2_JAZZY_MIGRATION_RESEARCH_AND_PLAN.md` (untracked pre-existing user file);
- source package, URDF, world, SDF, sensor, bridge, Web UI, dan backend.

## 4. Phase 0 — interface contract

Contract lengkap ada di [`docs/ROS_INTERFACE_CONTRACT.md`](docs/ROS_INTERFACE_CONTRACT.md).

Baseline yang dicatat:

- effective `ROS_DOMAIN_ID` pada Compose: `42`;
- rosbridge WebSocket: `0.0.0.0:8765`;
- web video server: `:8080`;
- backend: `:3001`;
- Vite/Web UI development server: `:3000`;
- launch chain utama: `amr_bringup` → `amr_simulation` → `gazebo_ros` Classic;
- SLAM chain: `slam_toolbox`;
- navigation chain: `nav2_bringup`;
- Web UI tetap bergantung pada rosbridge dan topic/service custom yang sudah ada.

Topic, service, action, custom message/service fields, TF tree, producer/consumer, dan real-robot mapping yang masih `TBD` sudah dicatat di contract.

Temuan baseline yang sengaja tidak diperbaiki pada Phase 0/1:

- `amr_docking/scripts/docking_manager_node.py` memakai nama field `StationConfig` yang berbeda dari `StationConfig.srv` yang committed;
- Web UI memanggil `/robot_mode`, tetapi provider-nya belum ditemukan pada bringup saat ini;
- Web UI publish `/amr/mission_payload`, tetapi subscriber-nya belum ditemukan;
- komentar tertentu menyebut Foxglove, sementara bringup aktual memakai rosbridge.

Temuan ini menjadi pekerjaan cleanup/adapter terpisah agar perubahan foundation tidak mencampur perubahan perilaku aplikasi.

## 5. Phase 1 — Docker Jazzy/Noble foundation

Perubahan utama:

- base image: `ros:jazzy-ros-base-noble`;
- package ROS diganti ke namespace `ros-jazzy-*` untuk core, Nav2, SLAM, rosbridge, web video, TurtleBot3, dan runtime node;
- modern Gazebo foundation ditambahkan: `ros-jazzy-ros-gz-sim`, `ros-jazzy-ros-gz-bridge`, `ros-jazzy-ros-gz-image`;
- `GZ_SIM_RESOURCE_PATH` ditambahkan untuk jalur modern;
- `GAZEBO_MODEL_PATH` dipertahankan hanya sebagai compatibility variable untuk source Gazebo Classic yang belum dimigrasikan;
- default `BUILD_WORKSPACE=false`, sehingga Docker build memvalidasi `colcon list` tetapi tidak menyamarkan kegagalan dependency workspace;
- entrypoint source `/opt/ros/jazzy/setup.bash` dan optional workspace overlay;
- Compose image diubah menjadi `amr-sim:jazzy`;
- `FOUNDATION_ONLY=true` menjadi default Compose;
- healthcheck menggunakan Bash untuk source ROS Jazzy sebelum menjalankan `ros2 --help`;
- `scripts/install_ros2.sh` sekarang hanya memeriksa Ubuntu Noble + Docker/Compose dan tidak menginstal atau menghapus ROS native di host.

Host yang diverifikasi: Ubuntu 24.04.4 LTS Noble. ROS 2 host tidak diperlukan karena environment disediakan container.

## 6. Referensi Humble/Jammy yang diubah dan dipertahankan

Diubah:

- Docker base image Humble/Jammy → Jazzy/Noble;
- semua source/setup path helper Docker dari `/opt/ros/humble` → `/opt/ros/jazzy`;
- apt package prefix `ros-humble-*` → `ros-jazzy-*`;
- image Compose `amr-sim:humble` → `amr-sim:jazzy`.

Dipertahankan dengan sengaja:

- dependency key dan launch/plugin path `gazebo_ros`/`gazebo_ros_pkgs` pada source package;
- Gazebo Classic launch, URDF, world, SDF, dan plugin source;
- `GAZEBO_MODEL_PATH` compatibility variable;
- optional source `/tmp/opennav_ws` pada `scripts/build_ws.sh`;
- referensi historis pada dokumen migrasi.

Alasannya: Phase 1 hanya menyediakan foundation. Menghapus atau mengganti referensi tersebut tanpa migrasi paket dan runtime akan menghasilkan perubahan perilaku yang tidak tervalidasi.

## 7. Dependency status

Detail dan evidence ada di [`docs/JAZZY_DEPENDENCY_STATUS.md`](docs/JAZZY_DEPENDENCY_STATUS.md).

Klasifikasi yang dipakai:

- **A — available/validated**: tersedia di image Jazzy dan/atau prefix dapat diverifikasi;
- **B — available but migration validation pending**: paket ada, tetapi integrasi source belum diuji pada fase ini;
- **C — blocked**: key/path lama tidak dapat di-resolve atau memerlukan porting;
- **D — not used in current Phase 0/1**;
- **E — unavailable/unknown in current apt/rosdep check**.

Hasil aktual `rosdep install --from-paths src --ignore-src -y --rosdistro jazzy`:

```text
amr_docking: Cannot locate rosdep definition for [opennav_docking_msgs]
amr_simulation: Cannot locate rosdep definition for [gazebo_ros_pkgs]
```

Jadi full workspace belum dapat dibangun secara sah sebelum package manifests dan integrasi Gazebo/docking ditangani pada fase berikutnya.

## 8. Validation matrix

| Validation | Status | Evidence |
|---|---|---|
| Host Ubuntu codename | PASS | `Ubuntu 24.04.4 LTS`, codename `noble` |
| Docker engine/Compose available | PASS | image build dan `docker compose config` berjalan |
| Docker image build foundation | PASS | `Image amr-sim:jazzy Built` |
| ROS distro in image | PASS | `ROS_DISTRO=jazzy`, `ROS_VERSION=2` |
| `ros2 --help` | PASS | berhasil pada standalone container dan Compose container |
| Workspace discovery | PASS | `colcon list` menemukan 5 package |
| `custom_interfaces` build | PASS | `1 package finished` |
| Required modern package prefixes | PASS | `ros_gz_sim`, `ros_gz_bridge`, `nav2_bringup`, `slam_toolbox`, `rosbridge_server`, `web_video_server` → `/opt/ros/jazzy` |
| Compose syntax/config | PASS | `docker compose config --quiet` |
| Compose foundation container | PASS | service `amr-sim` running, health `healthy` |
| Compose ROS domain | PASS | container smoke check: `ROS_DOMAIN_ID=42` |
| Full rosdep workspace resolution | BLOCKED | unresolved `gazebo_ros_pkgs` dan `opennav_docking_msgs` |
| Full workspace build | BLOCKED | tidak dijalankan setelah rosdep blocker; tidak boleh diklaim PASS |
| Full Gazebo/Web UI/SLAM/Nav2 runtime | NOT TESTED | sengaja ditunda sesuai scope Phase 0/1 |
| Native ROS installation on host | NOT TESTED | Docker-first decision; tidak diperlukan |

Command-level checks juga lulus shell syntax untuk:
`scripts/build_ws.sh`, `scripts/docker_run.sh`, `scripts/install_ros2.sh`, dan `docker/entrypoint.sh`.

## 9. Dampak aplikasi

Tidak ada source Web UI atau backend yang diubah. Port, host networking, rosbridge endpoint, web video endpoint, backend endpoint, volume map/source, dan database mode update dipertahankan.

Namun, menjalankan simulasi penuh dengan `FOUNDATION_ONLY=false` masih berisiko gagal karena bringup aktual masih memanggil Gazebo Classic. Helper `up`, `slam`, `nav`, dan `teleop` sekarang memberi pesan bahwa migrasi Gazebo harus selesai; helper tersebut tidak mengklaim runtime lama sudah Jazzy-compatible.

## 10. Blocker dan risiko untuk fase berikutnya

Blocker utama:

1. `gazebo_ros_pkgs` tidak memiliki rosdep definition yang dapat di-resolve pada Jazzy dan source masih menggunakan Classic launch/plugin API.
2. `opennav_docking_msgs` tidak memiliki rosdep definition yang dapat di-resolve pada environment ini; docking custom saat ini belum sama dengan OpenNav Docking.

Risiko yang harus ditangani sebelum runtime penuh:

- update package manifests dan custom nodes ke dependency/API Jazzy;
- pilih serta implementasi Gazebo Sim Harmonic launch + `ros_gz_bridge` berdasarkan interface contract;
- validasi `/clock`, `/tf`, `/scan`, odom, camera, `cmd_vel`, dan lifecycle Nav2;
- validasi SLAM dan navigation terhadap world/robot hasil porting;
- audit dan cleanup mismatch custom docking/UI yang sudah dicatat;
- baru setelah itu uji mode server sendiri dan mini computer robot.

## 11. Diff summary dan handoff

`git diff --stat` untuk tracked files saat report ini dibuat:

```text
 docker-compose.yml      |  24 +++++---
 docker/Dockerfile       |  69 ++++++++++++++---------
 docker/entrypoint.sh    |  10 ++--
 scripts/build_ws.sh    |  12 ++--
 scripts/docker_run.sh  |  26 +++++----
 scripts/install_ros2.sh | 142 +++++++-----------------------------------------
 6 files changed, 106 insertions(+), 177 deletions(-)
```

`git diff --stat` tidak menghitung file baru yang masih untracked; tiga dokumen baru dicantumkan pada bagian file berubah. Tidak ada file yang di-stage atau di-commit.

Kesimpulan: Phase 0 dan Phase 1 selesai dalam scope yang disetujui. Foundation Jazzy/Noble reproducible dan terverifikasi, sedangkan full workspace/simulasi secara eksplisit masih BLOCKED/ditunda. Pekerjaan berhenti di sini menunggu persetujuan untuk Phase 2 (package manifest dan custom-node compatibility), lalu fase migrasi Gazebo.

## 12. Referensi resmi

- [ROS 2 Jazzy binary installation for Ubuntu Noble](https://docs.ros.org/en/jazzy/Installation/Alternatives/Ubuntu-Install-Binary.html)
- [Gazebo Classic to modern Gazebo migration guidance](https://gazebosim.org/docs/all/migrating_gazebo_classic_ros2_packages/)
- [ROS 2 integration with Gazebo Harmonic](https://gazebosim.org/docs/harmonic/ros2_integration/)
