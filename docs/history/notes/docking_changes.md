# Docking System — Changelog & Architecture

## Overview

Sistem docking AGV terdiri dari tiga lapisan:

```
Web UI (Vue 3)
  └─ DockingPanel.vue      — kontrol dock/undock, manage dock stations
  └─ MapView.vue           — placement dock di peta (click+drag untuk yaw)
  └─ useROS.js             — bridge ke ROS via rosbridge
        │
        ├─ /station_config (service)   — register station ke node
        └─ /dock_command   (service)   — trigger dock/undock/cancel

ROS Node (Python)
  └─ docking_manager_node.py — state machine + reverse velocity control
        │
        ├─ NavigateToPose (action)     — Nav2 ke approach point
        ├─ /cmd_vel (publisher)        — reverse mundur ke dock
        └─ /dock_status (topic)        — broadcast state ke UI
```

---

## Perubahan yang Dilakukan

### 1. Yaw Support pada Dock Placement (MapView.vue + App.vue)

**Sebelum:** Dock placement hanya click biasa, yaw selalu `0.0` hardcoded.

**Sesudah:** Step 0 (target dock) pakai **click + drag** seperti `initial_pose` — muncul panah amber, yaw dihitung dari arah drag (`atan2(dy, dx)`). Step 1 (approach) tetap click biasa, yaw otomatis sama dengan target.

**File:** `web-ui/src/components/MapView.vue`, `web-ui/src/App.vue`

**Alasan:** Robot harus tiba di approach point dengan orientasi yang benar sebelum mundur ke dock. Yaw approach = yaw target supaya robot tinggal reverse lurus.

---

### 2. Race Condition Fix: configStation sekarang di-await (DockingPanel.vue + useROS.js)

**Sebelum:** `ros.configStation()` dipanggil fire-and-forget. User bisa langsung klik "Send to Dock" sebelum `/station_config` service call selesai → error `station not registered`.

**Sesudah:** `configStation()` return `Promise`, di-`await` di `addDock()`. Tombol tetap loading sampai station berhasil di-register di ROS node.

**File:** `web-ui/src/composables/useROS.js`, `web-ui/src/components/DockingPanel.vue`

---

### 3. Fase NAVIGATING_TO_DOCK: Nav2 → cmd_vel Reverse (docking_manager_node.py)

**Sebelum:** `_do_dock()` pakai `NavigateToPose` Nav2 → robot maju ke titik dock, bukan mundur.

**Sesudah:** `_do_dock()` publish `cmd_vel` langsung dengan `linear.x = -0.15 m/s` (reverse), control loop 10 Hz via timer.

**File:** `ros2_ws/src/amr_docking/scripts/docking_manager_node.py`

**State machine sekarang:**
```
IDLE
  ↓ dock command
NAVIGATING_TO_APPROACH  — Nav2 (dengan yaw benar di approach)
  ↓ arrived
NAVIGATING_TO_DOCK      — cmd_vel reverse langsung
  ↓ odom traveled ≥ (initial_dist - threshold)
DOCKED ✓
  ↓ undock command
UNDOCKING               — Nav2 kembali ke approach
  ↓ arrived
IDLE
```

---

### 4. Collision Monitor Bypass (docking_manager_node.py)

**Masalah:** `collision_monitor` (Nav2) publish `velocity=0` ke `/cmd_vel` ketika mendeteksi obstacle di arah gerak. Dock terdeteksi sebagai obstacle → robot direm sebelum sampai.

**Solusi:** Tambah lifecycle client ke `/collision_monitor/change_state`. Saat reverse dimulai, collision_monitor di-deactivate. Setelah docked/error/cancel, di-activate kembali.

**Catatan:** Service `service_is_ready()` dipakai (non-blocking) karena `wait_for_service()` dari dalam callback akan block spin thread.

---

### 5. Distance Tracking: amcl_pose → odom delta (docking_manager_node.py)

**Masalah:** `/amcl_pose` tidak publish saat robot reverse pelan (AMCL punya `update_min_d` threshold). `self._current_pose` stale → jarak ke dock tidak pernah berkurang → robot terus mundur tanpa berhenti.

**Solusi:** Tambah subscriber `/odom` (30-50 Hz, selalu update). Saat reverse dimulai:
1. Catat `initial_dist` = jarak approach→dock dari `amcl_pose` yang fresh
2. Track `odom_traveled` = jarak yang sudah ditempuh dari odom position delta
3. Stop ketika `odom_traveled >= initial_dist - DOCK_THRESHOLD`

**File:** `ros2_ws/src/amr_docking/scripts/docking_manager_node.py`

```
amcl_pose: ~1 Hz saat bergerak, bisa 0 Hz saat lambat  ← TIDAK reliable untuk reverse
odom:      30-50 Hz, selalu update                      ← dipakai untuk reverse tracking
```

---

### 6. Navigate Mode: Yaw via Drag (MapView.vue + useROS.js)

**Sebelum:** Klik di map langsung kirim navigasi dengan `theta=0` hardcoded.

**Sesudah:** Click + drag → panah biru → yaw dari arah drag. Click biasa → navigasi tanpa yaw (Nav2 tentukan orientasi sendiri, kirim quaternion identity).

**File:** `web-ui/src/components/MapView.vue`, `web-ui/src/composables/useROS.js`

---

### 7. View Mode sebagai Default (MapView.vue + useMapMode.js)

**Sebelum:** Mode default = `navigate` → klik sembarang di map langsung kirim robot.

**Sesudah:** Mode default = `view` (pan only). Navigate mode hanya aktif kalau button Navigate di-klik. Setelah goal dikirim, otomatis balik ke `view`.

Toolbar ditambah button **Hand (Pan/View)** di atas Navigate.

**File:** `web-ui/src/composables/useMapMode.js`, `web-ui/src/components/MapView.vue`

---

### 8. Robot Marker Rotation Fix (MapView.vue)

**Masalah:** CSS `transform-origin` default = `50% 50%` (center element). Body robot ada di `(ox, oy)` bukan center element (ada arrow di atas menambah tinggi SVG). Saat robot rotate, body visual melenceng dari posisi sebenarnya.

**Solusi:** Set `el.style.transformOrigin = "${anchorX}px ${anchorY}px"` sebelum apply rotate, di mana `[anchorX, anchorY]` = `iconAnchor` dari icon = body center robot.

**File:** `web-ui/src/components/MapView.vue`

---

## Parameter Docking (docking_manager_node.py)

| Parameter | Value | Keterangan |
|---|---|---|
| `_REVERSE_SPEED` | 0.15 m/s | Kecepatan mundur |
| `_DOCK_THRESHOLD` | 0.20 m | Sisa jarak sebelum dinyatakan DOCKED |
| `_REVERSE_TIMEOUT` | 30.0 s | Batas waktu reverse sebelum ERROR |

---

## Topics & Services

| Name | Type | Arah | Fungsi |
|---|---|---|---|
| `/dock_command` | `custom_interfaces/srv/DockCommand` | UI → Node | Trigger dock/undock/cancel |
| `/station_config` | `custom_interfaces/srv/StationConfig` | UI → Node | Register/hapus dock station |
| `/dock_status` | `std_msgs/String` | Node → UI | Broadcast state (IDLE/NAVIGATING/DOCKED/ERROR) |
| `/cmd_vel` | `geometry_msgs/Twist` | Node → Robot | Reverse velocity saat NAVIGATING_TO_DOCK |
| `/odom` | `nav_msgs/Odometry` | Robot → Node | Distance tracking saat reverse |
| `/amcl_pose` | `geometry_msgs/PoseWithCovarianceStamped` | AMCL → Node | Pose robot (untuk undock offset & initial_dist) |
| `/collision_monitor/change_state` | `lifecycle_msgs/srv/ChangeState` | Node → Nav2 | Pause collision monitor saat reverse |
