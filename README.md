# AMR Simulation + Web UI

ROS2 Humble + Gazebo simulation stack dengan Vue 3 web control interface.

> **Setup**: ROS2 Humble berjalan di Docker (Ubuntu 24.04 host tidak support Humble natively).
> Web UI dan Backend berjalan native di host.

---

## Quick Start

### Prerequisites
```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # re-login setelah ini
```

### 1. Build Docker image (sekali saja, ~10-15 menit)
```bash
bash scripts/docker_run.sh build
```

### 2. Start Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 3001 --reload
```

### 3. Start Web UI
```bash
bash scripts/setup_webui.sh
# Buka http://localhost:3000
```

### 4. Pertama kali buka Web UI
Startup dialog akan muncul otomatis — pilih mode operasi:

- **Mapping** → Docker start SLAM mode, robot siap di-teleop untuk membuat peta
- **Navigation** → Pilih map yang tersimpan, Docker start Nav2 mode

### 5. Kontrol manual dari terminal (opsional)
```bash
bash scripts/docker_run.sh slam          # SLAM / mapping mode
bash scripts/docker_run.sh nav amr_map.yaml  # Navigation mode dengan map
bash scripts/docker_run.sh teleop        # SLAM + keyboard teleop
bash scripts/docker_run.sh save-map amr_map  # Simpan map ke maps/
bash scripts/docker_run.sh down          # Stop semua container
bash scripts/docker_run.sh logs          # Lihat logs container
bash scripts/docker_run.sh shell         # Buka shell di container
```

---

## Architecture

```
Browser (Vue 3 :3000)
     │ HTTP REST
FastAPI Backend (:3001) ──── SQLite DB (/data/amr.db)
     │
     │ WebSocket :8765
rosbridge_websocket
     │
ROS2 Humble (Docker)
  ├── Gazebo Classic + TurtleBot3 (waffle_pi)
  ├── slam_toolbox          (SLAM mapping, /tf map→odom @50Hz)
  ├── Navigation2 (Nav2)
  │   ├── navigate_to_pose
  │   ├── follow_waypoints
  │   ├── velocity_smoother + collision_monitor
  │   └── keepout_filter (costmap)
  ├── opennav_docking
  ├── mission_manager_node  (custom action server)
  └── web_video_server :8080
```

---

## Project Structure

```
ros-software/
├── ros2_ws/src/
│   ├── amr_simulation/       # Gazebo world, sim.launch.py, slam.launch.py
│   │   └── config/slam_params.yaml
│   ├── amr_navigation/       # Nav2 params, keepout config, mission_manager_node.py
│   ├── amr_docking/          # opennav_docking config + docking_manager_node.py
│   ├── amr_bringup/          # Master launch (bringup.launch.py)
│   └── custom_interfaces/    # MissionPlan.action, DockCommand.srv, StationConfig.srv
├── web-ui/
│   └── src/
│       ├── App.vue                      # Main layout, mode switch, startup dialog
│       ├── composables/
│       │   ├── useROS.js                # roslibjs wrapper (TF, pose, teleop, actions)
│       │   └── useAPI.js                # HTTP API wrapper (FastAPI :3001)
│       ├── stores/robot.js              # Pinia state (pose, map, mission, docking)
│       └── components/
│           ├── MapView.vue              # Leaflet + OccupancyGrid + TF robot marker
│           ├── MissionPanel.vue         # Waypoints + mission execution
│           ├── MappingPanel.vue         # SLAM teleop joystick + save map
│           ├── DockingPanel.vue         # Auto-dock control
│           └── SetupPanel.vue           # Map manager + destination editor
├── backend/
│   ├── main.py
│   ├── database.py                      # SQLite init + settings table
│   ├── models.py
│   └── routers/
│       ├── maps.py          # GET/POST/DELETE maps
│       ├── missions.py      # CRUD missions
│       ├── destinations.py  # CRUD destination points
│       ├── docks.py         # CRUD dock stations
│       ├── keepout.py       # CRUD keepout zones
│       └── mode.py          # GET/POST mode switch (persisted ke DB)
├── maps/                    # Map files (.yaml + .pgm) — persisten di host
├── scripts/
│   ├── docker_run.sh        # Build/run/stop Docker helper
│   ├── install_ros2.sh      # Setup ROS2 (non-Docker)
│   ├── build_ws.sh          # Build ros2_ws
│   └── setup_webui.sh       # npm install + dev server
└── docs/
```

---

## Web UI Features

### Mode Operasi

| Mode | Deskripsi |
|---|---|
| **Mapping** | SLAM Toolbox aktif. Gerakkan robot via joystick/dpad untuk membangun peta |
| **Navigation** | Nav2 aktif. Robot navigasi otonom menggunakan peta tersimpan |

**Startup dialog** muncul otomatis saat pertama kali membuka Web UI — pilih mode dan map (jika navigation). Mode dipersist ke DB sehingga refresh halaman akan kembali ke mode yang sama.

**Mode switch** (tombol di header) — menampilkan konfirmasi sebelum restart ROS nodes:
- Navigation → pilih map dari dropdown sebelum konfirmasi
- Mapping → konfirmasi saja, SLAM dimulai dari awal

---

### Semua Fitur

| Feature | Cara Pakai |
|---|---|
| **Startup mode selection** | Dialog otomatis saat pertama load — pilih Mapping atau Navigation + map |
| **Mode switch (Header)** | Klik tombol Navigation/Mapping → confirm dialog → Docker restart otomatis |
| **View map** | Map render otomatis dari topic `/map` |
| **Robot position** | Marker robot update real-time via TF chain `map→odom→base_footprint` (~30Hz) |
| **Navigate** | Klik peta di mode "Navigate" atau isi koordinat di panel |
| **Set initial pose** | Mode "Init Pose" di peta (click + drag arah) |
| **Add waypoint** | Mode "Waypoint" → klik peta |
| **Add destination point** | Setup tab → "+ Add" → klik peta, pilih tipe (Pick/Drop/P&D) |
| **Run mission** | Mission tab → pilih destination → tambah ke waypoints → Start |
| **Loop mission** | Enable Loop + isi Count (0=∞) → Start |
| **Manual waypoint** | Set Mode=Manual → robot berhenti di titik, klik "Confirm" untuk lanjut |
| **Pause / Stop** | Pause: batalkan goal aktif; Stop: hentikan seluruh mission |
| **Teleop (Mapping mode)** | Mapping tab → joystick pad atau D-pad |
| **Speed preset** | Slow / Normal / Fast di panel Mapping |
| **Draw keepout zone** | Mode "Keepout" di peta → draw polygon → Finish |
| **Auto dock** | Docking tab → pilih dock station → Send to Dock |
| **Save map** | Mapping panel → isi nama → Save Map |
| **Load/activate map** | Setup tab → Maps → Activate |
| **Camera feed** | Klik "Show Camera Feed" di bottom bar |
| **E-STOP** | Tombol merah di header — kirim `cmd_vel` zero seketika |
| **Battery indicator** | Header — persentase + indikator charging |

---

## ROS Topics & Services

### Subscriptions (UI ← Robot)

| Topic | Type | Keterangan |
|---|---|---|
| `/map` | `nav_msgs/OccupancyGrid` | Peta occupancy grid — QoS: transient_local |
| `/tf` | `tf2_msgs/TFMessage` | TF transforms — dipakai untuk pose robot `map→odom→base_footprint` |
| `/tf_static` | `tf2_msgs/TFMessage` | Static TF (sensor frames, dll) |
| `/amcl_pose` | `geometry_msgs/PoseWithCovarianceStamped` | Fallback pose jika TF belum tersedia (navigation mode) |
| `/pose` | `geometry_msgs/PoseWithCovarianceStamped` | Fallback pose dari SLAM Toolbox (mapping mode) |
| `/odom` | `nav_msgs/Odometry` | Kecepatan linear/angular robot (twist only) |
| `/plan` | `nav_msgs/Path` | Path yang direncanakan Nav2 |
| `/scan` | `sensor_msgs/LaserScan` | Data laser untuk visualisasi |
| `/particle_cloud` | `nav2_msgs/ParticleCloud` | Partikel AMCL (navigation mode) |
| `/robot_description` | `std_msgs/String` | URDF XML — diparse untuk footprint robot — QoS: transient_local |
| `/global_costmap/costmap` | `nav_msgs/OccupancyGrid` | Costmap Nav2 — throttle 500ms |
| `/dock_status` | `std_msgs/String` | `idle` \| `navigating_to_approach` \| `docked` \| `undocking` \| `error` |
| `/battery_state` | `sensor_msgs/BatteryState` | Persentase baterai — throttle 1000ms |
| `/mission_plan/_action/status` | `action_msgs/GoalStatusArray` | Status goal mission |
| `/mission_plan/_action/feedback` | `custom_interfaces/action/MissionPlan_FeedbackMessage` | Feedback teks navigasi |

### Publications (UI → Robot)

| Topic | Type | Keterangan |
|---|---|---|
| `/goal_pose` | `geometry_msgs/PoseStamped` | Navigasi single point |
| `/cmd_vel` | `geometry_msgs/Twist` | Teleop — publish tiap 80ms saat joystick/dpad aktif |
| `/initialpose` | `geometry_msgs/PoseWithCovarianceStamped` | Set pose awal AMCL |
| `/amr/keepout_zones` | `std_msgs/String` (JSON) | `[{ polygon:[{x,y},…] }]` — dikirim tiap zona berubah atau reconnect |

### Actions (UI → Robot)

| Action | Type | Keterangan |
|---|---|---|
| `/mission_plan` | `custom_interfaces/action/MissionPlan` | Eksekusi satu waypoint per goal — UI kirim goal berikutnya setelah result `SUCCESS` |
| `/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | Single-point navigation (non-mission) |

### Services (UI → Robot)

| Service | Type | Keterangan |
|---|---|---|
| `/dock_command` | `custom_interfaces/srv/DockCommand` | `action: "dock"/"undock"/"cancel"` |
| `/station_config` | `custom_interfaces/srv/StationConfig` | Save/delete dock station ke ROS |
| `/mission_confirm` | `std_srvs/srv/Trigger` | Konfirmasi manual waypoint untuk lanjut |
| `/map_saver/save_map` | `nav2_msgs/srv/SaveMap` | Simpan map ke file |
| `/map_server/load_map` | `nav2_msgs/srv/LoadMap` | Load map ke Nav2 |

---

## Backend REST API (FastAPI :3001)

### Mode

| Method | Endpoint | Body | Keterangan |
|---|---|---|---|
| GET | `/api/mode` | — | Mode aktif saat ini (`slam`/`navigation`) + `map_file` |
| POST | `/api/mode/switch` | `{ mode, map_file? }` | Switch mode — stop container lama, start baru. Mode dipersist ke DB |

### Maps

| Method | Endpoint | Body | Keterangan |
|---|---|---|---|
| GET | `/api/maps` | — | Daftar semua map tersimpan |
| POST | `/api/maps/upload` | `FormData { yaml_file, pgm_file }` | Upload map baru |
| POST | `/api/maps/{id}/activate` | — | Aktifkan map |
| DELETE | `/api/maps/{id}` | — | Hapus map |

### Missions, Destinations, Docks, Keepout

| Method | Endpoint | Keterangan |
|---|---|---|
| GET/POST | `/api/missions` | Daftar / simpan mission |
| DELETE | `/api/missions/{id}` | Hapus mission |
| GET/POST | `/api/destinations` | Daftar / buat destination point |
| PUT/DELETE | `/api/destinations/{id}` | Update / hapus destination |
| GET/POST | `/api/docks` | Daftar / buat dock station |
| PUT/DELETE | `/api/docks/{id}` | Update / hapus dock |
| GET | `/api/keepout` | Daftar keepout zone |
| DELETE | `/api/keepout/{id}` | Hapus keepout zone |

---

## Mode Switch Flow

```
User klik Navigation/Mapping
        │
        ▼
Confirm dialog muncul
  [Mapping]              [Navigation]
  Warning misi batal     Dropdown pilih map
        │                      │
        ▼                      ▼
POST /api/mode/switch   POST /api/mode/switch
  { mode: "slam" }        { mode: "navigation",
                            map_file: "/maps/xxx.yaml" }
        │
        ▼
Backend:
  1. docker_run.sh down   ← stop container lama
  2. docker_run.sh slam   ← atau nav [map]
  3. Simpan mode ke SQLite
        │
        ▼
ROS reconnect → UI sync mode dari backend
```

**Startup (pertama kali / fresh install):**
```
App load → GET /api/mode
  ├── mode belum di-set → tampilkan Startup Dialog
  │     [Mapping] atau [Navigation + pilih map] → Mulai
  └── mode sudah di-set → apply langsung (no dialog)
```

---

## Development Notes

- **Pose source priority**: `TF map→base_footprint` (30Hz, via `/tf`) → `/amcl_pose` (fallback nav) → `/pose` SLAM Toolbox (fallback mapping)
- **TF tidak butuh `tf2_web_republisher`** — roslibjs subscribe langsung ke `/tf` dan `/tf_static` via rosbridge
- **SLAM params**: `minimum_travel_distance: 0.1` — scan match tiap 10cm agar pose update lebih smooth
- **Mode persistence**: Disimpan di SQLite table `settings` (`ros_mode`, `ros_map_file`) — survive backend restart
- **Map files**: Disimpan di `./maps/` (Docker volume mount) — persisten di host
- **Foxglove Bridge / rosbridge**: Port `8765` — accessible dari device lain di network yang sama
- **Camera stream**: `http://robot-ip:8080/stream?topic=/camera/image_raw`
- **Keepout zones**: Disimpan di database, dikirim ulang ke ROS saat reconnect
- **Mission timeout watchdog**: 120 detik per waypoint — auto-advance jika tidak ada status update
- **Manual waypoint mode**: Robot berhenti setelah tiba, tunggu call `/mission_confirm` sebelum lanjut
# ros2-software-amr
