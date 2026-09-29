# Rencana Integrasi — Isaac Sim (mesin 192.168.2.133)

Tujuan terdekat: **membuat map dari simulasi Isaac Sim lewat Web UI kita**, lalu
menaikkannya ke registry map.

Dokumen ini dibaca dua pihak. Tahap 1 berisi langkah di mesin Isaac Sim
(`gspe-ai3@192.168.2.133`) — itu bagian tim simulasi. Tahap 2 berisi pekerjaan di
repo ini.

Status: **rencana, belum dieksekusi.** Tidak ada satu file pun di mesin
192.168.2.133 yang diubah saat survei ini dibuat.

---

## 1. Ringkasan temuan

Semua di bawah ini hasil pemeriksaan langsung (read-only) pada 2026-09-29.

| Hal | Temuan |
|---|---|
| Distro | ROS 2 **Jazzy**, Ubuntu 24.04.3 — sama dengan kita, jadi penamaan plugin Nav2 `::` konsisten |
| `ROS_DOMAIN_ID` | **10** (dipaksa oleh launch file mereka) |
| `slam_toolbox` | terpasang |
| `nav2_map_server` | terpasang — `map_saver_cli`, `map_saver_server`, `costmap_filter_info_server` tersedia |
| `topic_tools` | **tidak** terpasang |
| Orkestrator | `/master_control` (C++, `master_control` pkg) — sudah memegang service yang sama dengan agent kita |
| Map aktif di `map_server` | `amr_description/share/amr_description/map/maze_restaurant.yaml` |

### 1.1 Rencana "shim TF" dibatalkan

Sebelumnya kami merancang node tambalan untuk menyambung pohon TF. **Tidak
diperlukan.** `/tfff` dan `/tfr` yang aneh itu publisher internal Isaac yang
tidak dipakai siapa pun. Pohon TF yang sebenarnya dibangun oleh dua node di
launch file mereka sendiri:

```
odom       → base_link              ekf_filter_node   (ekf_cfg.yaml: publish_tf: true)
base_link  → chassis, top_cover, RPLIDAR_S2E, gprp_robot_IMU_link,
             gprp_robot_LIDAR_C1_link, Realsense, left_wheel, right_wheel, caster×4
                                    robot_state_publisher (robot.urdf)
```

Pohonnya utuh, dan `/scan` (frame `RPLIDAR_S2E`) tersambung ke `base_link`.
Kemarin `/tf` tidak ada semata karena launch file itu belum pernah dijalankan.

### 1.2 Satu blocker nyata di sisi mereka

`amr_description/config/slam_cfg.yaml` baris 41:

```yaml
base_frame: base_footprint
```

`robot.urdf` yang dimuat `robot_state_publisher` **tidak punya link
`base_footprint`**. Link itu masih ada di `robot_base.xacro:100` dan di
`robot.urdf.bak`, jadi `robot.urdf` pernah diregenerasi dari sumber Isaac dan
link tersebut hilang.

Akibatnya `slam_toolbox` terus gagal melakukan lookup `odom → base_footprint`
dan `/map` tidak pernah terbit. Gejalanya menipu: node hidup, tidak ada error
mencolok, peta kosong saja.

### 1.3 `/master_control` — sebagian masih kerangka

Nama service/action-nya identik dengan milik kita, tapi dua handler yang paling
kita butuhkan belum berisi apa-apa (`master_control/src/master_control_node.cpp`):

| Fungsi | Status |
|---|---|
| `mission_goal_handle` / docking (`main_algorithm.cpp`, 670 baris) | jalan, tersambung ke `/navigate_to_pose`, `/dock_robot`, `/undock_robot` |
| `station_config_handle` | **stub** — log lalu balas `"OK"`, tidak menyimpan apa pun |
| `robot_mode_handle` | **stub** — string disimpan ke `robot_mode_`, tidak dipakai |
| `send_lifecycle_cmd` | **badan kosong** (`(void)client; (void)command; (void)label;`) |

`send_lifecycle_cmd` kosong berarti `/master_control` tidak bisa menyalakan atau
mematikan Nav2 — jadi tidak ada pergantian mode map↔nav di sisi mereka, dan SLAM
tidak pernah dijalankan olehnya.

---

## 2. Keputusan: dua tahap, agent belakangan

Agent (`robot_agent_node.py`) **tidak** dipasang di tahap 1.

Alasannya bukan soal usaha, tapi karena dua blocker di §4 (tabrakan nama service
dengan `/master_control`, dan `/map_saver/save_map` yang tidak ada di sana)
membuat agent yang dipasang hari ini **tidak akan bisa menyimpan map** sekaligus
**berebut service** dengan orkestrator mereka. Memasangnya sekarang menambah satu
lapis masalah di atas pipeline yang belum pernah terbukti jalan.

Tahap 1 tidak butuh agent sama sekali dan sudah cukup untuk membuat map.

---

## 3. Tahap 1 — bikin map tanpa agent

### 3.1 Di mesin Isaac Sim — untuk tim simulasi

**Langkah 1. Betulkan `base_frame`.** Satu baris, di
`src/amr_description/config/slam_cfg.yaml`:

```yaml
base_frame: base_link      # sebelumnya base_footprint, link itu tidak ada di robot.urdf
```

Lalu:

```bash
cd ~/ros2_gprp_amr_ws
colcon build --packages-select amr_description
```

> Alternatif yang lebih benar untuk jangka panjang: regenerasi `robot.urdf` dari
> `robot.urdf.xacro` supaya `base_footprint` kembali (standar REP-120). Tapi itu
> menyentuh seluruh rantai frame Isaac, jadi jangan sekarang.

**Langkah 2. Nyalakan Isaac Sim** (robot + world seperti biasa).

**Langkah 3. Jalankan launch mapping:**

```bash
ros2 launch amr_description amr_mapping_sim_launch.py
```

Yang ikut hidup: `robot_state_publisher`, `ekf_filter_node`, `slam_toolbox`
(autostart, lifecycle langsung aktif), `master_control`, dan rosbridge.

**Langkah 4. Samakan port rosbridge.** Default launch itu **8765**, sedangkan
Web UI sekarang terhubung ke **9090**. Pilih salah satu:

```bash
# opsi A — ikuti default launch, ubah port di entry robot Web UI jadi 8765
ros2 launch amr_description amr_mapping_sim_launch.py

# opsi B — pertahankan 9090, tidak perlu ubah Web UI
ros2 launch amr_description amr_mapping_sim_launch.py websocket_port:=9090
```

**Langkah 5. Cek pohon TF sudah utuh** sebelum lanjut:

```bash
ros2 run tf2_tools view_frames        # harus: map → odom → base_link → RPLIDAR_S2E
ros2 topic hz /map                    # harus ada terbitan
```

### 3.2 Di sisi kita

Tidak ada perubahan kode. Cukup pastikan URL rosbridge pada entry robot cocok
dengan port yang dipilih di Langkah 4.

### 3.3 Menyimpan map

Agent belum ada, jadi penyimpanan dilakukan manual lalu diunggah:

```bash
# di mesin Isaac Sim, sementara slam_toolbox masih jalan
ros2 run nav2_map_server map_saver_cli -f ~/namamap
```

Hasilnya `namamap.pgm` + `namamap.yaml`. Salin ke laptop, lalu **unggah lewat
fitur upload di halaman `/maps`** yang sudah ada. Map masuk registry seperti map
lain.

### 3.4 Kriteria selesai tahap 1

- [ ] `view_frames` menunjukkan `map → odom → base_link` tersambung
- [ ] `/map` terbit dan tergambar live di Web UI
- [ ] peta terbentuk saat robot dijalankan di Isaac Sim
- [ ] `.pgm` + `.yaml` tersimpan dan berhasil diunggah ke registry
- [ ] map hasil unggah bisa di-assign ke robot

---

## 4. Tahap 2 — pasang agent (hanya setelah tahap 1 lulus)

Empat blocker, semuanya sudah teridentifikasi.

### (a) Nama package di-hardcode — *kerja di repo kita*

`ros2_ws/src/amr_bringup/scripts/robot_agent_node.py:1300`

```python
"ros2", "launch", "amr_simulation", "slam.launch.py",
"ros2", "launch", "amr_navigation", "navigation.launch.py",
```

Dua package itu tidak ada di mesin mereka. Harus jadi parameter node, supaya
bisa diisi `amr_description` + `amr_mapping_sim_launch.py` /
`amr_navigation_sim_launch.py`.

### (b) Tabrakan nama service dengan `/master_control` — **paling serius**

`/master_control` sudah melayani `/robot_mode`, `/station_config`,
`/mission_plan`, `/dock_command`, dan menerbitkan `/robot_status`. Agent kita
menyediakan nama yang sama.

Dua server pada satu nama service itu perilakunya **tidak terdefinisi** — tidak
ketahuan siapa yang menjawab, dan tidak ada pesan error. Keduanya juga akan
sama-sama mengirim goal ke Nav2.

Harus pilih satu, sadar-sadar:

- matikan orkestrator mereka: `launch_master_control:=false` (argumennya sudah ada), atau
- jalankan agent kita di namespace tersendiri dan arahkan Web UI ke sana

### (c) `RobotStatus.msg` tidak cocok di wire — *kerja di repo kita*

Kompatibilitas pesan ROS 2 dihitung dari definisi lengkapnya, bukan nama field.
Nama tipe sama (`custom_interfaces/msg/RobotStatus`), isinya beda:

| | Punya kita | Punya mereka |
|---|---|---|
| Jumlah field | 6 | 17 |
| Hanya ada di kita | `robot_undocked` | — |
| Hanya ada di mereka | — | `start_point_pos`, `end_point_pos`, `start_point`, `end_point`, `robot_current_station`, `running_count`, `lidar_status`, `imu_status`, `driver_motor_status`, `tfmini_status`, `ultrasonic_status` |

Rencana: **kita** mengadopsi definisi mereka (mereka yang di robot asli, dan
field-nya lebih lengkap), lalu **menambahkan `robot_undocked`** supaya milik kita
tidak hilang. Sekalian `battery_voltage` / `battery_percentage` kita yang selama
ini selalu 0 jadi ada isinya.

Perlu koordinasi satu kali: setelah field ditambah, **kedua** mesin harus
rebuild `custom_interfaces`.

### (d) `/map_saver/save_map` tidak ada di sana

Agent kita memanggil service itu
(`robot_agent_node.py:173`, `MAP_SAVER_SERVICE`). `slam_launch.py` mereka hanya
menjalankan `slam_toolbox` — tidak ada node `map_saver`.

`map_saver_server` tersedia di sana, jadi pilihannya: agent ikut menjalankannya,
atau launch mapping mereka yang menambahkannya.

---

## 5. Yang perlu disepakati sebelum ditulis — bisa merusak data

`StationConfig.srv` field `action` tidak bernomor di komentar mereka
("add / delete"), sedangkan milik kita `0=delete, 1=save`.

Kalau urutannya ternyata kebalik, **perintah simpan station akan menghapus
station** — tanpa error, data hilang diam-diam. Sekarang masih aman karena
`station_config_handle` mereka baru stub, tapi harus disepakati sebelum diisi.

Hal yang sama untuk `type`: kita `0=Pick, 1=Drop, 2=Pick&Drop, 3=Charging`,
komentar mereka cuma "pick / drop, charging".

---

## 6. Sengaja tidak dikerjakan sekarang

| Hal | Alasan |
|---|---|
| Node shim TF | Tidak perlu — `ekf_node` + `robot_state_publisher` sudah menyediakannya (§1.1) |
| Regenerasi `robot.urdf` agar `base_footprint` kembali | Menyentuh seluruh rantai frame Isaac; §3.1 langkah 1 cukup untuk sekarang |
| Menyatukan zone filter | Mereka pakai `/costmap_filter_info` tunggal, kita tiga (`/zone_keepout_filter_info`, `/zone_speed_filter_info`, `/zone_binary_filter_info`). Satu info topic hanya bisa membawa satu `type`, jadi setup mereka cuma mendukung satu jenis zone. Bukan blocker mapping |
| Mengadopsi `route_server`, `docking_server`, `detour_obstacle_layer` mereka | Fitur yang belum kita punya; catat, jangan campur ke jalur mapping |

---

## 7. Catatan operasional

**`use_sim_time` dan `/clock`.** Saat survei, semua node di sana
`use_sim_time: True` sementara `/clock` tidak punya publisher (Isaac baru
dimatikan) — 31 node beku, waktunya tidak maju, TF selalu dianggap kedaluwarsa.
Untuk Isaac Sim ini benar selama sim hidup. Untuk robot fisik harus relaunch
dengan `use_sim_time:=false`.

**Nama node ganda.** `ros2 node list` di sana melaporkan
`WARNING: ... nodes in the graph that share an exact name` — ada 2×
`rosbridge_websocket` dan 3× `rviz`. Sisa proses lama. Bersihkan sebelum
mengukur apa pun, supaya angka pub/sub tidak menyesatkan.

---

## 8. Hasil eksekusi — 2026-09-29

Tahap 1 dan Tahap 2 keduanya **selesai dan terbukti**. Urutan yang benar-benar
dijalankan, beserta buktinya.

### 8.1 Yang diubah di mesin Isaac Sim

Hanya satu file, seperti rencana:

```diff
  # src/amr_description/config/slam_cfg.yaml:40-41
- # Frame dasar robot pada permukaan lantai (base_footprint)
- base_frame: base_footprint
+ # Frame dasar robot (base_link; robot.urdf tidak punya base_footprint)
+ base_frame: base_link
```

Backup: `slam_cfg.yaml.bak.20260929`. **`colcon build` tidak diperlukan** —
`install/` di sana memakai symlink ke `src/`, satu langkah di §3.1 jadi gugur.

Agent ditempatkan di `~/amr_agent/` (bukan di dalam workspace mereka, karena
bukan package colcon dan tidak perlu di-build):

```
/home/gspe-ai3/amr_agent/
├── robot_agent_node.py
├── backend_client.py      harus bersebelahan — sys.path ikut lokasi script
└── run_agent_gprp.sh      runner, semua parameter di dalam
```

Dijalankan dengan dua argumen:

```bash
~/amr_agent/run_agent_gprp.sh <robot_id> http://<ip-backend>:3002
```

### 8.2 Perubahan di repo ini

Blocker §4 ternyata **tiga, bukan empat**: agent tidak memakai `RobotStatus`
sama sekali, jadi §4(c) bukan penghalang untuk memasangnya.

| Perubahan | File |
|---|---|
| Nama launch package/file jadi parameter, default tetap seperti semula | `robot_agent_node.py` |
| `map_save_via`: `service` (default) atau `cli` | `robot_agent_node.py` |
| `_record_intent` — `/robot_mode` menulis balik ke registry | `robot_agent_node.py` |
| `REGISTRY_TO_MODE` / `MODE_TO_REGISTRY` — `idle` ↔ `stop` | `robot_agent_node.py` |
| `set_desired_mode()` | `backend_client.py` |
| Runner untuk stack gprp | `run_agent_gprp.sh` (baru) |

Dua bug ditemukan sebelum dijalankan, dan keduanya akan menggagalkan survey:

**Intent tidak tersimpan.** `/robot_mode` tidak menulis `desired_mode`, dan
`robotsApi.setMode` di frontend nol pemanggil. Tanpa perbaikan, sync loop
menarik robot kembali ke `nav` sepuluh detik setelah survey dimulai — dan
tombol Save menolak dengan `REJECTED: not mapping`.

**Kosakata beda.** Registry memakai `idle`, agent memakai `stop`.
`_reconcile_mode` menolak apa pun di luar `map|nav|stop`, jadi robot yang
di-park lewat registry tidak pernah direkonsiliasi. Nilai yang tidak bisa
diterjemahkan sekarang diprotes, bukan diabaikan diam-diam.

**Jangan pakai `slam_toolbox/srv/SaveMap` sebagai pengganti.** Service itu hanya
menerima `std_msgs/String name`, jadi format gambar, threshold dan lokasi file
ikut konfigurasi node tersebut. Registry butuh PGM trinary di path yang agent
tentukan. Menjalankan `map_saver_server` sendiri juga bukan jalan keluar: itu
lifecycle node dan diam di `unconfigured` sampai ada yang men-transisi.
`map_saver_cli` mengurus configure+activate sendiri lalu keluar — itu yang
dipakai `map_save_via: cli`.

### 8.3 Bukti end-to-end

Survei "Cafe1", disimpan lewat tombol Save di Web UI, tanpa langkah manual:

```
registry   Cafe1  v1  24a2b073  323×234  created_by_robot=7fc87960
robot      ~/map_cache/24a2b073-.../map.pgm + map.yaml
assign     active_map_id = 24a2b073-...       (otomatis)
agent      mode=unknown state=idle "Stopped on request"
registry   desired_mode = idle

md5 robot    ba14623a1fb6d2ac944f98867ccce867
md5 registry ba14623a1fb6d2ac944f98867ccce867
sha256 file  8e437c272411555ca201a57602266aaf432a79f228d294f9da0246ab50579756
content_hash 8e437c272411555ca201a57602266aaf432a79f228d294f9da0246ab50579756
```

Direktori `.staging` bersih setelah save, jadi `_adopt_into_cache` + `rmtree`
berjalan sebagaimana mestinya.

---

## 9. Masalah terbuka: peta miring

Peta hasil survei **miring** — koridor yang dipetakan belakangan terpasang
menyudut terhadap yang lebih awal. Ini bukan soal tampilan; geometrinya memang
salah, dan peta yang miring akan membuat Nav2 merencanakan jalur ke tempat yang
keliru.

### 9.1 Ukurannya

```
map → odom    translasi (0.588, -0.450) m
              rotasi    5.199°
peta          323 × 234 @ 0.05  →  16.2 m × 11.7 m
```

`map → odom` adalah koreksi yang **sudah** ditempel SLAM ke odometry. 5.2° itu
yang berhasil dibetulkan; kemiringan yang terlihat adalah sisanya. Pada bentang
16 m, 5.2° berarti sekitar 1.5 m meleset di ujung.

### 9.2 Penyebab utama: EKF mengambil yaw dari roda

`amr_description/config/ekf_cfg.yaml`:

```yaml
odom0_config:  yaw  = TRUE     # "kunci orientasi mutlak roda agar tidak drift saat diam"
               vyaw = FALSE    # "cegah slip roda kastor Isaac Sim saat putar di tempat"
imu0_config:   yaw  = false
               vyaw = TRUE     # gyro Z
```

Ini kontradiksi. `vyaw` dari roda dimatikan karena kastor Isaac diketahui selip
saat berputar — tetapi `yaw` mutlak dari roda tetap dinyalakan, dan isinya
integral dari selip yang sama.

Gyro hanya menyumbang `vyaw`. **Laju tidak bisa mengoreksi bias mutlak.** Jadi
tidak ada sumber yang membetulkan yaw, dan filter justru mengunci diri ke
sumber yang paling mudah melenceng.

Komentarnya benar untuk satu kasus sempit: roda memang tidak melayang saat robot
**diam**. Tapi drift lahir saat **berbelok**, dan di situ yaw roda adalah yang
terburuk.

**Perbaikan yang diusulkan — satu nilai:**

```yaml
odom0_config: [false, false, false,
               false, false, false,    # yaw: TRUE -> false
               true,  false, false,
               false, false, false,
               false, false, false]
```

Setelah itu yaw menjadi integral gyro Z, yang di Isaac Sim hampir bebas noise.
Orientasi absolut diurus SLAM lewat `map -> odom` — memang itu tugasnya.

Di robot fisik, bias gyro BNO055 akan terintegrasi. Itu pun lebih baik daripada
selip roda, dan tetap dikoreksi SLAM.

### 9.3 Faktor pendukung

**Clock Isaac tersendat.** Isaac dijalankan dengan
`--/app/runLoops/main/rateLimitEnabled=false`, sehingga `/clock` maju
tersendat — kadang satu langkah, kadang enam. Gejalanya di log:

```
[ekf_filter_node] Failed to meet update rate! Took 0.20000001 s
[slam_toolbox]    Message Filter dropping message: frame 'RPLIDAR_S2E'
```

Durasi yang dilaporkan selalu kelipatan bulat 1/30 detik — ciri granularitas
langkah simulasi, bukan beban CPU (mesin 75% idle saat itu diukur). Saat EKF
melewatkan slot, `odom -> base_link` tidak segar dan scan dicocokkan pada pose
basi.

**`minimum_travel_heading: 0.5`** rad = 28.6°. SLAM baru menambah node setelah
robot berputar hampir 29°. Justru belokan yang melahirkan error, dan di situ
node-nya paling jarang. Sekitar 0.2 rad memberi lebih banyak kendala di tempat
yang paling membutuhkannya.

`loop_search_maximum_distance: 3.0` juga kecil untuk peta 16 m, tetapi ini yang
paling lemah dari ketiganya dan tidak diklaim sebagai penyebab.

### 9.4 Status: perbaikan yaw sudah diterapkan

`ekf_cfg.yaml` sudah diubah (backup `ekf_cfg.yaml.bak.20260929`, md5 asli
`7006bda94933e77944043e928c1b2bdd`). Hasilnya:

```
odom0_config = [False, False, False,    x, y, z
                False, False, False,    r, p, yaw     <- tadinya True
                True,  False, False,    vx, vy, vz    <- hanya ini dari roda
                False, False, False,    vr, vp, vyaw
                False, False, False]    ax, ay, az
```

Tidak perlu `colcon build`: `install/` memakai symlink ke `src/`.

**Hanya satu variabel yang diubah.** `minimum_travel_heading` dan rate limiting
Isaac sengaja dibiarkan, supaya kalau peta masih miring setelah survei ulang,
jelas mana yang belum cukup. Mengubah tiga hal sekaligus menghilangkan
kemampuan itu.

### 9.5 Yang wajib dicek sebelum mempercayai hasilnya

Perubahan ini membuat **gyro menjadi satu-satunya sumber yaw**. Kalau IMU Isaac
tidak menerbitkan angular velocity yang benar, robot tidak akan pernah berputar
di peta — kegagalan yang lebih buruk daripada miring.

Saat survei dimulai, sebelum menempuh jarak jauh, putar robot di tempat dan
jalankan:

```bash
ros2 topic echo /imu --field angular_velocity.z
```

Nilainya harus bergerak jelas dari nol dan berganti tanda mengikuti arah putar.
Kalau tetap nol atau sangat kecil, kembalikan `ekf_cfg.yaml` dari backup dan
laporkan — artinya IMU Isaac perlu diperiksa lebih dulu, dan perbaikan yaw harus
menunggu.

Saat survei ini ditulis, pemeriksaan tersebut **belum bisa dilakukan**: Isaac dan
agent sudah dimatikan, sehingga `/imu` tidak terbit. Yang diketahui hanya bahwa
topiknya hidup pada dua sesi sebelumnya (51.9 Hz dan 52.6 Hz); isinya belum
pernah diperiksa.

### 9.6 Langkah kedua: gyro saja ternyata melayang saat diam

Perbaikan §9.4 menyembuhkan selip saat berbelok, tetapi menyisakan gyro sebagai
**satu-satunya** sumber yaw — dan gyro Isaac punya bias DC.

Terukur dengan robot benar-benar diam:

```
gyro /imu angular_velocity.z   mean -0.00285 rad/s  (n=40, sd 0.0024)

13:45:36   odom->base -23.548   map->base -23.791   map->odom -0.000
13:45:48   odom->base -24.058   map->base -24.273   map->odom -0.000
13:46:03   odom->base -24.580   map->base -24.773   map->odom -0.000
                      --------
                      -1.032 derajat / 27 detik  =  -2.3 derajat/menit
```

`/odom` twist hanya ±0.003 rad/s, jadi robot **tidak berputar secara fisik**.
Yang berputar adalah perkiraan arah hadapnya.

`map->odom` bertahan di **-0.000** sepanjang pengamatan: SLAM tidak
mengoreksinya sama sekali, karena `minimum_travel_distance: 0.5` dan
`minimum_travel_heading: 0.5` tidak pernah terpicu oleh robot yang tidak
bergerak. Drift-nya tumbuh tanpa ada yang menahan, dan laser digambar pada arah
hadap yang sudah salah.

Komentar asli di config mereka benar untuk kasus ini — "kunci orientasi mutlak
roda agar tidak drift saat diam" — dan sempat ditampik terlalu cepat.

**Perubahan kedua:** `odom0_config` vyaw dinyalakan.

```
odom0_config = [F F F   F F F   T F F   F F T   F F F]
                x y z   r p yaw  vx vy vz  vr vp vyaw  ax ay az
imu0_config  = [F F F   F F F   F F F   F F T   F F F]
```

Yaw kini disusun dari dua sumber **laju**, tanpa sudut mutlak dari roda sama
sekali. Saat robot diam, encoder membaca nol persis, dan itu bukti kuat "tidak
sedang berputar" yang menekan bias gyro. Sebuah laju tidak terakumulasi, jadi
selip kastor tidak menumpuk menjadi kesalahan tak berbatas seperti pada yaw
mutlak.

Backup, jangan tertukar:

| File | Isi |
|---|---|
| `ekf_cfg.yaml.bak.20260929` | asli — yaw mutlak roda, tanpa vyaw |
| `ekf_cfg.yaml.bak.20260929-step1` | langkah 1 — gyro saja |
| aktif | langkah 2 — vyaw roda + vyaw gyro |

### 9.6b KOREKSI: bukan bias gyro, dan langkah 2 salah

Pengukuran langsung pada data mentah Isaac — tanpa agent, tanpa SLAM, tanpa EKF,
robot benar-benar diam, simulasi berjalan — membatalkan diagnosis §9.6.

Kontrol lebih dulu, memastikan simulasi tidak beku:

```
wall clock 12.01 s   /clock maju 10.433 s   rasio 0.869   -> SIM JALAN
```

Lalu, 1042 sampel selama 20 detik:

```
/imu angular_velocity.x/y/z   mean 0.000000  sd 0.000000  min=max=0
/imu linear_acceleration      (-0.000014, +0.007865, +9.809998)  sd 0.000000
/odom twist.angular.z         -0.002780942  KONSTAN (626 sampel, 1 nilai unik)
/odom twist.linear.x          +0.001079855  KONSTAN
/odom pose.yaw                -0.0473 -> -0.0473 deg, delta 0.00000 dalam 17.4 s
```

**IMU Isaac tidak punya bias sama sekali** — nilainya nol presisi, tanpa noise.
Klaim "bias DC -0.00285 rad/s" di §9.6 salah.

Yang rusak justru **`/odom` milik Isaac**: `twist` melaporkan kecepatan sudut dan
linier konstan bukan-nol selamanya, sementara `pose` yang diterbitkan pesan yang
sama tidak bergerak sedikit pun. Twist-nya berbohong; pose-nya jujur.

**Akibatnya langkah 2 (`odom0 vyaw = true`) justru merusak.** EKF akan
mengintegrasikan -0.002781 rad/s itu terus-menerus:

```
-0.002781 rad/s = -0.159 deg/s = -9.6 deg/menit
```

Empat kali lebih buruk daripada -2.3 deg/menit yang hendak diperbaiki.
**Langkah 2 dibatalkan**, konfigurasi dikembalikan ke langkah 1
(`ekf_cfg.yaml.bak.20260929-step1`, md5 `4c3ab08c257068c4ba6ab8cd08cfe1d8`).

Konfigurasi yang berlaku sekarang, dan yang benar untuk Isaac:

```
odom0_config = [F F F   F F F   T F F   F F F   F F F]   hanya vx
imu0_config  = [F F F   F F F   F F F   F F T   F F F]   hanya vyaw
```

IMU-nya bersih, jadi yaw dari integral gyro tidak melayang saat robot diam.
Tidak ada sudut mutlak dari roda, jadi selip kastor tidak terakumulasi.

**Sisa yang diketahui:** `odom0 vx` masih menyerap residu `+0.001080 m/s`, yang
kalau diintegrasikan menjadi sekitar 6.5 cm/menit pergeseran posisi. Jauh lebih
ringan daripada kesalahan yaw, dan scan matching mengoreksi posisi lebih mudah
daripada arah hadap. Dibiarkan.

**Perbaikan yang sebenarnya ada di sisi Isaac:** odometry graph mereka harus
mengembalikan `twist` ke nol saat robot berhenti. Selama tidak, setiap konsumen
`/odom` twist akan melayang.

### 9.6c Masih terbuka: kenapa robot berputar saat idle

Belum terjawab. Yang diketahui:

- Saat gejala muncul, `/imu` angular_velocity.z **bukan** nol (terbaca 0.0079,
  0.0107, -0.0082 rad/s). IMU Isaac tanpa noise, jadi nilai bukan-nol berarti
  robot **memang benar-benar berputar**, bukan sekadar perkiraannya melayang.
- `/cmd_vel` saat itu 19.99 Hz dan `/teleop/cmd_vel` 12.08 Hz. Sekarang
  keduanya tidak ada publisher-nya sama sekali.
- `TELEOP_PUBLISH_HZ = 12`, dan halaman survey memang menerbitkan aliran tetap
  selama mapping aktif — nilainya nol ketika tidak sedang dikemudikan. Jadi
  topic yang aktif **bukan** bukti adanya perintah bukan-nol.
- Jalur gamepad sudah dijaga: `STICK_DEADZONE = 0.12`, dan `onSample` hanya
  menghasilkan twist bukan-nol ketika deadman ditahan.

Artinya dugaan "gamepad drift" **tidak didukung kode**. Nilai
`/teleop/cmd_vel` yang sebenarnya belum pernah terukur — pengukurannya gagal
timeout, dan sesudah itu UI sudah ditutup.

Langkah berikutnya: jalankan survei, jangan sentuh apa pun, lalu ukur
`angular.z` pada `/teleop/cmd_vel` dan `/cmd_vel`. Kalau nol sementara robot
tetap berputar, penyebabnya di Isaac. Kalau bukan nol, penyebabnya di UI kita.

### 9.6d KESIMPULAN: robot tidak berputar, laporannya yang bohong

Diukur saat SLAM dan agent berjalan, tanpa menyentuh kendali apa pun.

**Perintah gerak nol presisi — UI kita bersih:**

```
/teleop/cmd_vel  linear.x  dan  angular.z   0.000000  (264 sampel, sd 0)
/cmd_vel         linear.x  dan  angular.z   0.000000  (480 sampel, sd 0)
```

Dugaan "gamepad drift" dan "UI mengirim perintah" **terbantah**.

**Dua pengukuran independen membuktikan robot diam:**

```
/odom POSE yaw     -0.05190 -> -0.05129 deg   delta +0.00061 deg / 24.9 s
/odom POSE posisi  (-0.0003,-0.0002) -> (-0.0003,-0.0002)   geser 0.0000 m
sudut dinding dari /scan   +1.0 -> +0.5 deg   (1.0, 0.5, 0.5, 0.5, 0.5, 1.0)
```

**Tetapi kecepatan sudut yang dilaporkan bukan nol:**

```
/odom twist.angular.z   -0.007902 rad/s
/imu  angular_velocity.z -0.008012 rad/s    <- identik, satu sumber
odom->base_link yaw     -6.73 -> -11.51 deg  = -13.07 deg/menit
map->odom               0.0000 sepanjang 22 detik, tidak ada koreksi
```

Jadi: **robot berdiri diam, Isaac melaporkan ia berputar**, EKF
mengintegrasikan laporan itu, dan UI menggambar robot beserta lasernya pada
arah hadap yang tidak pernah terjadi.

Catatan penting: ketika `/cmd_vel` tidak punya publisher sama sekali (agent
mati), semua nilai ini **nol presisi dengan sd 0**. Residu hanya muncul setelah
ada yang menerbitkan `/cmd_vel`, meskipun isinya nol. Itu menunjuk ke
controller Isaac yang aktif, bukan ke sensornya.

### 9.6e Akibatnya: semua perubahan EKF dibatalkan

Di Isaac, `/odom` **pose jujur** sementara `twist` dan `/imu` **bohong**.

Konfigurasi asli mereka memakai `odom0 yaw = true`, yaitu membaca **pose** —
sumber yang jujur. Perubahan §9.4 memindahkannya ke gyro, yaitu sumber yang
bohong, sehingga memperburuk keadaan. Komentar asli mereka benar, dan §9.2
keliru menyebutnya kontradiksi.

Konfigurasi **dikembalikan ke asli**, md5 `7006bda94933e77944043e928c1b2bdd`
terverifikasi sama dengan `ekf_cfg.yaml.bak.20260929`:

```
odom0_config = [F F F   F F T   T F F   F F F   F F F]   yaw (pose) + vx
imu0_config  = [F F F   F F F   F F F   F F T   F F F]   vyaw
```

Peringatan untuk robot fisik: di Isaac `/odom` pose mendekati ground truth,
jadi `odom0 yaw = true` aman. Pada robot nyata pose itu hasil dead reckoning
roda dan **memang** melayang, sehingga pilihan ini harus ditinjau ulang sebelum
dipakai di luar simulasi.

### 9.6f Yang masih belum dijelaskan

Drift 5.199 derajat pada survei "Cafe1" **tidak** dijelaskan oleh konfigurasi
EKF. `map->odom` adalah koreksi yang ditempel SLAM terhadap odometry; kalau
odometry Isaac mendekati ground truth, angka itu tumbuh karena estimasi SLAM
sendiri yang melenceng, bukan karena odometry.

Tersangka berikutnya, berurutan:

1. **Clock Isaac tersendat** (`rateLimitEnabled=false`) sehingga scan dicocokkan
   pada pose basi — sudah terlihat sebagai `Failed to meet update rate` dan
   `Message Filter dropping message`.
2. **`minimum_travel_heading: 0.5` rad (28.6 derajat)** — terlalu kasar, dan
   `map->odom` yang bertahan di 0.0000 selama 22 detik menunjukkan SLAM memang
   jarang dipicu.
3. Isaac harus mengembalikan `twist` dan `angular_velocity` ke nol saat robot
   berhenti. Selama tidak, setiap konsumen kedua nilai itu akan melayang.

### 9.6g TERVERIFIKASI: revert menyembuhkan drift saat diam

Diukur 30 detik, robot diam, SLAM berjalan, `ekf_cfg.yaml` sudah kembali asli.

```
/odom pose yaw        -0.0489 -> -0.0491 deg   =  -0.00 deg/menit   (kebenaran Isaac)
odom->base_link yaw   -0.0573 -> -0.0491 deg   =  +0.02 deg/menit   (hasil EKF)
map->odom              0.0000 ->  0.0000 deg   =  +0.00 deg/menit

/odom twist.angular.z  -0.008032 rad/s   <- masih bohong
/imu angular_velocity.z -0.008023 rad/s  <- masih bohong

sebelum revert: -13.07 deg/menit
sesudah revert:  +0.02 deg/menit
```

Isaac tetap melaporkan kecepatan sudut palsu, tetapi EKF kini berpegang pada
`yaw` mutlak dari pose yang jujur, sehingga laporan palsu itu tertimpa dan tidak
terakumulasi. Drift saat diam selesai.

Kesimpulan akhir untuk bagian ini: **konfigurasi asli sudah benar untuk Isaac
Sim.** Seluruh perubahan pada `ekf_cfg.yaml` dibatalkan; satu-satunya perbaikan
yang bertahan adalah `slam_cfg.yaml` `base_frame: base_link`, dan itu wajib
karena `robot.urdf` tidak punya link `base_footprint`.

### 9.6h Jawaban resmi dari penulis slam_toolbox

[Issue #586](https://github.com/SteveMacenski/slam_toolbox/issues/586) ditutup
sebagai *completed*. Pelapornya memakai **parameter default**, di simulasi, dan
gejalanya identik: peta berputar sendiri saat scan matching. Jawaban Steve
Macenski:

> "This is a not-so-uncommon issue with **trivialized environments**... there
> are either (1) **too few features to do effective scan-to-scan matching** on
> (or your odometry is really truly terrible)... (2) you've messed with the
> configs greatly and essentially **de-tuned** the system...
>
> it's an artifact of the **overwhelming 'perfectness' of the simulated
> environment** paired with **very few distinctive features** to lock the system
> into a solution... **that's an issue in simulation only**. Even then, if you
> made a more realistic environment that's not just an empty room, it quickly
> improves in performance if it has a **few unique items to latch onto**.
>
> I've personally mapped spaces up to 200,000 sqft with this system and **the
> provided default parameters** without a hiccup."

Jadi: **bukan bug, bukan salah konfigurasi, dan bukan masalah EKF.** Scene Isaac
yang terlalu bersih dan terlalu polos.

Perbandingan konfigurasi mereka dengan `mapper_params_online_async.yaml` bawaan
slam_toolbox menunjukkan file mereka **identik dengan default**, kecuali tiga
nilai yang diubah dalam sesi ini. Kritik pada `minimum_travel_heading: 0.5` dan
`loop_search_maximum_distance: 3.0` di §9.3 karena itu **tidak berdasar** —
keduanya default upstream.

### 9.6i Rangkuman pengukuran drift

`map -> odom` yaw adalah koreksi yang ditempel SLAM terhadap odometry. Karena
odometry Isaac mendekati ground truth, angka ini mengukur **kesalahan SLAM
sendiri**, bukan kesalahan odometry.

| Percobaan | `coarse_search_angle_offset` | `map -> odom` yaw |
|---|---|---|
| Survei "Cafe1" | 0.349 (20 derajat) | +5.199 |
| Rute kedua | 0.349 | -6.999 |
| Rute ketiga | 0.0873 (5 derajat) | **+2.151** |
| Rute keempat | 0.0873 | +3.142 |

Mempersempit jendela pencarian memang membantu (-6.999 menjadi +2.151), dan
arahnya sejalan dengan panduan komunitas: jendela dilebarkan untuk odometry
buruk, jadi dipersempit untuk odometry bagus. Tetapi hasilnya **tidak stabil**
antar rute, yang konsisten dengan penjelasan maintainer: masalahnya bukan
setelan, melainkan kurangnya ciri untuk dikunci.

### 9.6j Yang harus dikerjakan, berurutan

1. **Isi scene Isaac dengan benda tidak simetris** di koridor dan ruangan. Ini
   perbaikan yang sebenarnya, dan hanya tim simulasi yang bisa. Asetnya sudah
   tersedia di `GPRP_amr_Final/Restaurant1/SubUSDs/` (`SM_RackFrame`,
   `SM_CardBoxC`, `SM_BeamA`, dan puluhan lain) — tinggal ditempatkan.
2. **Tutup loop saat survei**: akhiri di titik awal, jangan berhenti di ujung
   koridor. `do_loop_closing: true` sudah aktif dengan
   `loop_search_maximum_distance: 3.0`.
3. Belum diuji, kandidat berikutnya:
   - `use_scan_matching: false` — di simulasi dengan odometry ground truth,
     scan matching tidak punya apa pun untuk dikoreksi dan hanya bisa menambah
     error. [Issue #677](https://github.com/SteveMacenski/slam_toolbox/issues/677)
     melaporkan peta membaik ketika scan matching dimatikan.
   - `ceres_loss_function: HuberLoss` — [issue #334](https://github.com/SteveMacenski/slam_toolbox/issues/334),
     maintainer menyebutnya menandakan masalah local minima pada optimizer.
     Menutupi gejala, bukan menyembuhkan.

**Kembalikan `coarse_search_angle_offset` dan `angle_variance_penalty` ke
default sebelum dipakai di robot fisik.** Di sana odometry melayang dan
lingkungan penuh ciri, dua-duanya kebalikan dari asumsi perubahan ini.

### 9.6k Peta yang melenceng belum tentu tidak terpakai

Ini belum diuji sama sekali dan seharusnya diuji lebih dulu sebelum menyetel
apa pun lagi.

Peta yang melenceng tetap **konsisten dengan dirinya sendiri**. Stasiun yang
diajarkan di peta itu tersimpan dalam frame yang sama melencengnya, dan robot
berangkat memakai peta yang sama, sehingga kesalahannya saling meniadakan.
AMCL pun melokalisasi terhadap dinding di sekitarnya, bukan terhadap seluruh
peta.

Yang benar-benar terganggu oleh kemiringan: menimpakan denah CAD, menyambung
peta dari sesi berbeda, dan jalur lurus yang sangat panjang.

**Jangan meluruskan peta dengan editor.** Peta adalah acuan geometri untuk
lokalisasi, bukan gambar. Dinding yang diluruskan dengan kuas tidak lagi cocok
dengan apa yang dilihat laser, dan lokalisasi justru memburuk. Editor untuk
membersihkan artefak — orang yang lewat, palet, pantulan — bukan untuk
membetulkan geometri.

### 9.7 Status: BELUM DIUJI

Langkah 2 dipasang tetapi stack sudah dimatikan sebelum sempat diuji. Yang
masih harus dikerjakan, berurutan:

1. Jalankan Isaac, agent, lalu Create map
2. **Diamkan robot 30 detik.** Ukur `odom -> base_link` yaw dua kali.
   Pembanding: -2.3 derajat/menit sebelum langkah 2; target mendekati nol.
   Kalau masih melayang, tersangkanya pindah ke bias IMU Isaac itu sendiri, dan
   perbaikannya ada di sisi Isaac, bukan di EKF.
3. Baru setelah itu: keliling rute mirip Cafe1, ukur `map -> odom` sebelum Save.
   Pembanding: **5.199 derajat** pada Cafe1. Di bawah 1 derajat berarti
   perbaikan yaw berhasil.

### 9.8 Rotasi seragam bukan drift

Peta yang tampak miring **seluruhnya** bukan tanda kerusakan. slam_toolbox
mendefinisikan frame `map` pada pose robot saat SLAM dimulai, bukan pada dinding
gedung. Robot yang diparkir menyudut menghasilkan peta yang menyudut, dan itu
terjadi pada semua SLAM.

Terbukti dari satu tangkapan layar: `x 0.00  y 0.00  theta 0.1` — robot belum
bergerak sedikit pun sementara petanya sudah diagonal. Peta miring tanpa
gerakan tidak mungkin drift.

Isaac menempatkan robot pada yaw sekitar 32 derajat terhadap sumbu dunia
(`/odom` orientasi z=0.27529 w=0.96136, sementara `/tfr` world->odom identitas).

Nav2 tidak terpengaruh sama sekali: stasiun, zona dan jalur hidup di frame yang
sama. Kalau ingin peta yang sejajar dinding, sejajarkan robot dengan koridor
utama **sebelum** menekan Create map.

Bedakan dari drift: **rotasi seragam** menyudutkan seluruh peta dan tidak
berbahaya; **drift** menyudutkan satu bagian terhadap bagian lain dan
geometrinya memang salah. `map->odom` selalu mulai dari nol, jadi angka itu
mengukur drift saja dan tidak terpengaruh arah hadap awal.

### 9.9 Bug UI yang ditemukan sepanjang pengujian

**Survei kedua tidak bisa dimulai.** Setelah survei dihentikan, SLAM mati dan
`/tf` ikut diam — keadaan istirahat yang memang dirancang agent. Dua detik
kemudian `budgetMs: 2000` terlampaui, link dinilai `stale`, dan
`StartSurveyDialog` memblokir robot dengan "Telemetry has gone quiet". Satu-satunya
jalan keluar adalah reload halaman.

Diperbaiki: `TopicSpec` mendapat `needsStack`, dipasang pada `tf` dan `costmap`
saja. `anyStale(healths, stackRunning)` mengabaikan topic itu ketika stack
memang tidak berjalan, dan `stackRunning` dibaca dari `/robot_mode_status` milik
agent — bukan ditebak dari lalu lintas topic, karena justru itu yang harus
dibedakan. `/scan` dan `/odom` sengaja tidak ditandai: keduanya datang dari
simulator atau hardware dan tetap terbit walau stack mati, sehingga diamnya
memang kerusakan. Dua test regresi menyertainya.

**Loop `registry wants stop` setiap 10 detik.** `_switch(MODE_STOP)` meninggalkan
agent pada `unknown/idle`, bukan mode bernama `stop`, sehingga pemeriksaan
"sudah sampai tujuan" tidak pernah cocok. Agent membongkar stack yang sudah mati
berulang-ulang. Laten sebelumnya karena registry belum punya kosakata `stop`;
pemetaan `idle -> stop` membuatnya bisa diminta dan membongkar celahnya.

### 9.10 Catatan

Peta yang sudah terlanjur miring **tidak bisa diluruskan** — sel hitamnya
kumulatif. Survei harus diulang dari nol, dan "Cafe1" diperlakukan sebagai
peta uji, bukan peta produksi.
