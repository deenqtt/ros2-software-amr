# Robot Status Analysis — Probe 2026-04-09

> Hasil probe langsung ke robot di `ws://192.168.0.193:8765`

---

## 1. Temuan: Topic `/robot_status` (BARU, AKTIF)

```
Topic   : /robot_status
Type    : custom_interfaces/msg/RobotStatus
QoS     : default (volatile)
```

### Field & Nilai saat probe (robot dalam kondisi **docked**)

| Field               | Type   | Nilai saat probe | Keterangan                          |
|---------------------|--------|-----------------|-------------------------------------|
| `robot_docked`      | bool   | `true`          | Robot sedang docked                 |
| `robot_undocked`    | bool   | `false`         | Robot belum undock                  |
| `charging_state`    | bool   | `false`         | Tidak charging meski docked         |
| `robot_current_sts` | uint8  | `0`             | Status numerik robot (lihat enum)   |

### Enum `robot_current_sts` (belum dikonfirmasi tim robot, perlu diclarify)

| Nilai | Dugaan status    |
|-------|-----------------|
| 0     | IDLE / STANDBY  |
| 1     | NAVIGATING      |
| 2     | DOCKING         |
| 3     | UNDOCKING       |
| 4     | CHARGING        |
| 5     | ERROR           |

> **PENTING**: Konfirmasi nilai enum ini ke tim robot. Saat ini hanya nilai `0` yang terobservasi.

---

## 2. Topic yang TIDAK AKTIF (digantikan `/robot_status`)

| Topic           | Type                       | Status di robot  |
|-----------------|----------------------------|------------------|
| `/dock_status`  | `std_msgs/String`          | **TIDAK AKTIF**  |
| `/battery_state`| `sensor_msgs/BatteryState` | **TIDAK AKTIF**  |

→ Kedua topic ini masih di-subscribe oleh UI tapi tidak ada data yang masuk dari robot.

---

## 3. Topic yang Masih Aktif

| Topic                      | Type                                    | Status  |
|----------------------------|-----------------------------------------|---------|
| `/robot_status`            | `custom_interfaces/msg/RobotStatus`     | ✅ AKTIF |
| `/amcl_pose`               | `geometry_msgs/PoseWithCovarianceStamped` | ✅ AKTIF |
| `/map`                     | `nav_msgs/OccupancyGrid`               | ✅ AKTIF |
| `/tf`                      | `tf2_msgs/TFMessage`                   | ✅ AKTIF |
| `/rosout`                  | `rcl_interfaces/msg/Log`               | ✅ AKTIF |
| `/diagnostics`             | `diagnostic_msgs/DiagnosticArray`      | ✅ AKTIF |
| `/odom`                    | `nav_msgs/Odometry`                    | ❓ tidak dapat data saat probe |
| `/scan`                    | `sensor_msgs/LaserScan`                | ❓ tidak dapat data saat probe |

---

## 4. Services yang Aktif

| Service            | Type                                 | Status  | Catatan                        |
|--------------------|--------------------------------------|---------|--------------------------------|
| `/dock_command`    | `custom_interfaces/srv/DockCommand`  | ✅ AKTIF | Request: `{action, station_id}` / Response: `{result}` |
| `/station_config`  | `custom_interfaces/srv/StationConfig`| ✅ AKTIF | Register/hapus station         |
| `/map_server/load_map` | `nav2_msgs/srv/LoadMap`          | ✅ AKTIF |                                |
| `/mission_confirm` | `std_srvs/srv/Trigger`               | ❌ TIDAK ADA | Perlu dicek ke tim robot   |

---

## 5. Dampak ke UI (`web-ui/`)

### Masalah Saat Ini

1. **Undock selalu disabled** — `_subscribeDockStatus()` di `useROS.js` subscribe ke `/dock_status` yang sudah tidak aktif. Akibatnya `store.dockingStatus` tidak pernah berubah ke `"docked"`, sehingga tombol Undock di `DockingPanel.vue:38` selalu disabled karena kondisi `store.dockingStatus !== 'docked'`.

2. **Battery tidak tampil** — `_subscribeBattery()` subscribe ke `/battery_state` yang tidak aktif. Namun field `charging_state` sudah ada di `/robot_status`.

3. **Charging state tidak terbaca** — Sebelumnya charging dideteksi dari `battery_state.power_supply_status`. Sekarang ada field `charging_state` langsung dari robot.

---

## 6. Perubahan yang Perlu Dilakukan di UI

### `useROS.js` — `_subscribeDockStatus()` → ganti ke `/robot_status`

```js
function _subscribeRobotStatus() {
  const topic = new ROSLIB.Topic({
    ros: _ros,
    name: '/robot_status',
    messageType: 'custom_interfaces/msg/RobotStatus',
    queueSize: 1,
  });
  topic.subscribe((msg) => {
    // Map ke dockingStatus store
    let storeStatus = 'idle';
    if (msg.robot_docked && !msg.robot_undocked) {
      storeStatus = 'docked';
    } else if (msg.robot_undocked) {
      storeStatus = 'idle';
    }

    // robot_current_sts override (konfirmasi enum dulu ke tim robot)
    // if (msg.robot_current_sts === 2) storeStatus = 'docking';
    // if (msg.robot_current_sts === 3) storeStatus = 'undocking';
    // if (msg.robot_current_sts === 5) storeStatus = 'error';

    store.setDockingStatus(storeStatus);
    
    // Update charging state dari field baru
    store.setBatteryCharging(msg.charging_state);
  });
}
```

### `robot.js` — Tambah action `setBatteryCharging`

```js
// Tambah action terpisah untuk charging state dari robot_status
function setBatteryCharging(charging) {
  batteryCharging.value = charging;
}
```

### `_subscribeAll()` — Ganti panggilan

```js
// Ganti: _subscribeDockStatus()
// Jadi:
_subscribeRobotStatus();
// _subscribeBattery() bisa dihapus jika /battery_state tidak ada
// atau tetap dipertahankan sebagai fallback
```

---

## 7. Pertanyaan untuk Tim Robot

1. **Enum `robot_current_sts`** — Berapa nilai untuk setiap state (idle, navigating, docking, undocking, charging, error)?
2. **`charging_state`** — Kenapa `false` meski `robot_docked = true`? Apakah charging hanya aktif saat kontak fisik terhubung?
3. **`/mission_confirm` service** — Apakah sudah diimplementasi di robot side?
4. **`/odom` dan `/scan`** — Apakah aktif? Mungkin tidak publish saat robot diam.
5. **Topic name untuk `/robot_status`** — Apakah nama topicnya fix `/robot_status` atau ada namespace seperti `/agv/robot_status`?
