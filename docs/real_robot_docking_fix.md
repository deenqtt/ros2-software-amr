# Real Robot Docking Fix — `ros2_amr_ws`

## Latar Belakang

Real robot (`192.168.0.193`) menggunakan workspace `ros2_amr_ws` yang terpisah dari simulasi (`ros-software`). Ketika fitur docking dicoba di real robot, ditemukan beberapa masalah:

1. Robot navigasi ke approach point tapi **posisinya tidak sesuai dengan titik di map**
2. Ketika sampai di approach point, robot **muter-muter terus tidak berhenti**
3. Robot **tidak pernah mundur ke dock** meskipun approach sudah tercapai
4. Saat station baru didaftarkan, dock command **tidak tahu koordinatnya**

Setelah analisa kode di `ros2_amr_ws/src/`, ditemukan bahwa arsitektur docking di real robot **belum diimplementasikan sama sekali** — semua callback kosong, koordinat tidak disimpan, dan ada beberapa bug di kode yang ada.

---

## Arsitektur Docking (Setelah Fix)

```
Web UI (Vue 3)
  └─ /station_config  (service) ── simpan koordinat approach + target ke JSON
  └─ /dock_command    (service) ── trigger dock / undock / cancel
          │
          ▼
  web_interface_node (C++)
          │
          ├─ load koordinat dari station_data.json
          ├─ NAVIGATING_TO_APPROACH ── NavigateToPose → Nav2 → approach point
          ├─ NAVIGATING_TO_DOCK     ── /cmd_vel reverse + track jarak via /odom
          └─ DOCKED / UNDOCKING / ERROR
```

### State Machine

```
IDLE
  ↓  dock_command action="dock"
NAVIGATING_TO_APPROACH  ── Nav2 jalan ke approach point (yaw benar)
  ↓  goal_response_callback — arrived
NAVIGATING_TO_DOCK      ── /cmd_vel linear.x = -0.10 m/s (mundur)
  ↓  odom_traveled >= (initial_dist - DOCK_THRESHOLD)
DOCKED ✓
  ↓  dock_command action="undock"
UNDOCKING               ── Nav2 kembali ke approach point
  ↓  arrived
IDLE

Dari state apapun:
  dock_command action="cancel" → stop_reverse + cancel Nav2 → IDLE
```

---

## Problem 1 — Approach Point Melenceng dari Map

### Gejala
Robot diperintah menuju approach point, tapi posisi yang dituju **berbeda dari titik yang ditampilkan di map UI**.

### Root Cause
Di `amr_bringup_launch.py` (baris 119–125) ada **static transform publisher** `map → odom` dengan yaw = 3.14 rad (180°):

```python
Node(
    package='tf2_ros',
    executable='static_transform_publisher',
    name='odom_static_transform_publisher',
    arguments=['0.0', '0.0', '0.0', '3.14', '0', '0', 'map', 'odom']
)
```

Saat `amr_nav_launch.py` dijalankan, **AMCL juga publish `map → odom`** secara dinamis (`tf_broadcast: True` di `amr_param.yaml`). Dua publisher untuk transform yang sama menyebabkan **konflik di TF2** — selama AMCL belum konverge atau kehilangan fix, TF 180° ini yang aktif, sehingga semua goal Nav2 dalam `map` frame dirotasi 180° sebelum dieksekusi.

### Solusi
**Hapus static TF publisher tersebut.** AMCL bertanggung jawab penuh untuk publish `map → odom`. Static TF ini tidak boleh ada jika AMCL aktif.

### File yang Diubah
`ros2_amr_ws/src/amr_bringup/launch/amr_bringup_launch.py`

```python
# DIHAPUS:
# Node(
#     package='tf2_ros',
#     executable='static_transform_publisher',
#     name='odom_static_transform_publisher',
#     arguments=['0.0', '0.0', '0.0', '3.14', '0', '0', 'map', 'odom']
# ),
```

---

## Problem 2 — Robot Muter-Muter di Approach Point

### Gejala
Robot berhasil sampai di sekitar approach point, tapi kemudian **terus berputar** di tempat tanpa berhenti.

### Root Cause
Di `amr_param.yaml`, DWB controller menggunakan critic `RotateToGoal` dengan konfigurasi:

```yaml
RotateToGoal.lookahead_time: -0.25   # ← nilai negatif = masalah
yaw_goal_tolerance: 0.075            # ← terlalu ketat (4.3°)
```

`lookahead_time` negatif membuat critic menghitung alignment yaw dari arah **belakang** path, bukan ke depan. Akibatnya robot rotate, overshoot target yaw, balik lagi, overshoot lagi — **oscillasi terus-menerus**.

`yaw_goal_tolerance: 0.075` (4.3°) juga terlalu ketat untuk real robot yang memiliki noise odometry dan lokalisasi — robot tidak pernah benar-benar dianggap "cukup lurus" untuk berhenti.

### Solusi
Ubah ke nilai yang stabil:

```yaml
RotateToGoal.lookahead_time: 0.0   # netral, tidak melihat ke belakang
yaw_goal_tolerance: 0.2            # ~11.5° — realistis untuk real robot
```

### File yang Diubah
`ros2_amr_ws/src/amr_bringup/config/amr_param.yaml`

---

## Problem 3 — Tidak Ada Docking State Machine

### Gejala
Robot sampai di approach point lalu **berhenti total** — tidak mundur ke dock, tidak ada feedback status, docking tidak pernah selesai.

### Root Cause
`web_interface_node.cpp` memiliki service server `/dock_command` yang menerima perintah docking, tapi implementasinya **tidak pernah selesai**:

```cpp
// Semua callback ini KOSONG:
void WebInterfaceNode::dock_command_callback(...)  { }  // tidak dikirim ke Nav2
void WebInterfaceNode::undock_command_callback(...) { }  // tidak ada undock logic
void WebInterfaceNode::goal_command_callback(...)   { }  // tidak handle arrival

// dock_command_handle pakai field yang tidak ada di SRV:
data = nlohmann::json::parse(request->command);  // 'command' tidak ada → compile error
```

Akibatnya node tidak bisa dikompilasi dengan benar, dan bahkan jika jalan, tidak akan melakukan apa-apa setelah terima dock command.

### Solusi
Implementasi lengkap docking state machine di C++ dalam `web_interface_node`:

- **`dock_command_handle`** — terima `action` + `station_id`, load koordinat dari JSON, trigger navigasi
- **`navigate_to_approach()`** — kirim `NavigateToPose` ke Nav2 dengan koordinat approach + yaw benar
- **`goal_response_callback()`** — deteksi arrival, transisi ke fase reverse
- **`start_reverse()`** — hitung jarak approach→dock, mulai timer 10Hz
- **`reverse_tick()`** — publish `/cmd_vel` reverse, cek timeout
- **`odom_callback()`** — track jarak yang sudah ditempuh via `/odom` (bukan `/amcl_pose` karena AMCL tidak update saat robot bergerak pelan)
- **`stop_reverse()`** — hentikan timer, publish zero velocity
- **`cancel_docking()`** — cancel semua, kembali ke IDLE

### Parameter Docking

| Parameter | Value | Keterangan |
|---|---|---|
| `REVERSE_SPEED` | 0.10 m/s | Kecepatan mundur — sesuaikan dengan robot |
| `DOCK_THRESHOLD` | 0.20 m | Sisa jarak sebelum dinyatakan DOCKED |
| `REVERSE_TIMEOUT` | 30.0 s | Batas waktu sebelum ERROR |

> Definisi ada di `web_interface_node.h` sebagai `static constexpr double`.

---

## Problem 4 — Koordinat Station Tidak Tersimpan

### Gejala
Meskipun station sudah didaftarkan via UI, saat dock command dikirim robot tetap tidak tahu posisi dock karena koordinat tidak ada di JSON.

### Root Cause
`station_config_handle` menerima semua field koordinat dari `StationConfig.srv` (`x_pose`, `y_pose`, `yaw_pose`, `x_approach`, `y_approach`, `yaw_approach`), tapi **hanya menyimpan `id`, `name`, `type`** ke JSON:

```cpp
// Sebelum — koordinat dibuang:
data["stations"].push_back({
    {"id",   station_id},
    {"name", station_name},
    {"type", station_type}
    // x_pose, y_pose, yaw, x_approach, y_approach, yaw_approach ← tidak disimpan!
});
```

### Solusi
Simpan semua field koordinat ke JSON:

```cpp
// Sesudah:
data["stations"].push_back({
    {"id",           request->id},
    {"name",         request->name},
    {"type",         request->type},
    {"x_pose",       request->x_pose},
    {"y_pose",       request->y_pose},
    {"yaw_pose",     request->yaw_pose},
    {"x_approach",   request->x_approach},
    {"y_approach",   request->y_approach},
    {"yaw_approach", request->yaw_approach}
});
```

Format JSON yang tersimpan:
```json
{
  "stations": [
    {
      "id": 1,
      "name": "Dock A",
      "type": 2,
      "x_pose": 1.5,
      "y_pose": 2.0,
      "yaw_pose": 1.57,
      "x_approach": 1.5,
      "y_approach": 2.7,
      "yaw_approach": 1.57
    }
  ]
}
```

---

## Problem 5 — `interface_init()` Dipanggil Dua Kali

### Gejala
Service server terdaftar dua kali → potensi duplikat atau crash saat startup.

### Root Cause
```cpp
// main() sebelumnya:
auto node = std::make_shared<...>("web_interface_node");
node->interface_init();   // ← panggilan pertama, return value dibuang

rclcpp::executors::MultiThreadedExecutor executor;
executor.add_node(node);

if (node->interface_init()) {  // ← panggilan kedua, duplikat!
    executor.spin();
}
```

### Solusi
```cpp
// main() sesudah:
auto node = std::make_shared<...>("web_interface_node");

rclcpp::executors::MultiThreadedExecutor executor;
executor.add_node(node);

if (node->interface_init()) {  // ← satu kali saja
    executor.spin();
}
```

---

## Files yang Diubah

| File | Perubahan | Rebuild? |
|---|---|---|
| `amr_bringup/launch/amr_bringup_launch.py` | Hapus static TF `map→odom` 180° | Tidak |
| `amr_bringup/config/amr_param.yaml` | `RotateToGoal.lookahead_time: 0.0`, `yaw_goal_tolerance: 0.2` | Tidak |
| `web_interface/include/.../web_interface_node.h` | `DockState` enum, member vars, function declarations baru | Ya |
| `web_interface/src/web_interface_node.cpp` | Full state machine, fix station_config coords, fix double init | Ya |
| `web_interface/CMakeLists.txt` | Tambah `nav_msgs` dependency | Ya |

---

## Cara Deploy ke Real Robot

```bash
# 1. Sync file dari laptop ke real robot
rsync -av /home/deden/Documents/dev/ros2_amr_ws/src/ iotman@192.168.0.193:~/ros2_amr_ws/src/

# 2. SSH ke real robot
ssh iotman@192.168.0.193

# 3. Build package yang berubah
cd ~/ros2_amr_ws
colcon build --packages-select web_interface
source install/setup.bash

# 4. Restart semua node
```

> Dry run sebelum sync (cek file apa saja yang berubah):
> ```bash
> rsync -avn /home/deden/Documents/dev/ros2_amr_ws/src/ iotman@192.168.0.193:~/ros2_amr_ws/src/
> ```

---

## Catatan untuk Web UI

`/dock_status` topic belum diimplementasikan — robot belum broadcast state (IDLE / NAVIGATING / DOCKED / ERROR) ke UI. Jika diperlukan untuk feedback di UI, tambahkan `std_msgs/String` publisher di `web_interface_node` yang publish setiap kali state berubah.
