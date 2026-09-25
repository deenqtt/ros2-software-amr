# Diagnosis Odometry, IMU, EKF, dan Kualitas Mapping

## Status

Dokumen ini adalah catatan diagnosis read-only. Tidak ada perubahan pada simulator teman, konfigurasi EKF, ROS contract, Web UI, atau backend sebagai bagian dari pemeriksaan ini.

Status temuan:

- Masalah dapat direproduksi secara observasi setelah joystick digerakkan.
- Jalur joystick `/cmd_vel` tidak terbukti macet.
- Sumber utama yang dicurigai adalah odometry, IMU, dan TF hasil EKF di komputer simulator.
- Perbaikan belum diterapkan.

## Gejala

Saat mapping dimulai, velocity pada Web UI awalnya relatif tenang. Setelah joystick digerakkan sebentar lalu dilepas:

1. Robot terlihat diam di simulator.
2. Grafik linear/angular velocity di Web UI kembali bergerak naik-turun.
3. Marker robot di Web UI tampak berputar sedikit-sedikit.
4. Hasil map menjadi kurang lurus atau mengalami distorsi rotasi.

## Arsitektur data yang terlibat

```text
Joystick Web UI
    ↓
rosbridge
    ↓
/cmd_vel
    ↓
Isaac simulator
    ├── /odom
    └── /imu
          ↓
      robot_localization / EKF
          ├── /odometry/filtered
          └── TF odom → base_link
                    ↓
              slam_toolbox
                    ├── /map
                    └── TF map → odom
```

Web UI tidak membuat map. Web UI membaca data ROS dan menampilkan hasilnya.

## Temuan yang diverifikasi dari Web UI

### Input joystick

`web-ui/src/components/MappingPanel.vue` menerbitkan command setiap 80 ms ketika joystick ditekan. Saat pointer dilepas, `_reset()` memanggil `ros.stopRobot()`.

`web-ui/src/composables/useROS.js` menerbitkan:

```text
/cmd_vel
geometry_msgs/Twist
```

Hasil listener langsung di komputer simulator menunjukkan:

```text
Saat joystick digerakkan:
linear.x/angular.z bernilai nonzero

Saat joystick dilepas:
linear.x = 0
angular.z = 0
```

Kesimpulan: command joystick kembali ke nol dan tidak terbukti stuck.

### Grafik velocity

`web-ui/src/composables/useROS.js` saat ini subscribe ke:

```text
/odom
nav_msgs/Odometry
```

Field yang dibaca:

```text
msg.twist.twist.linear.x
msg.twist.twist.angular.z
```

`web-ui/src/components/charts/SpeedChart.vue` menampilkan nilai tersebut tanpa deadband atau filtering signifikan. Karena itu, grafik mencerminkan noise dari `/odom` secara langsung.

### Pose robot di Web UI

Pose robot tidak diambil dari grafik velocity. `useROS.js` memprioritaskan TF:

```text
map → odom → base_footprint/base_link
```

Web UI menggunakan hasil TF untuk memperbarui posisi dan orientasi robot. Jika TF `odom → base_link` berubah ketika robot diam, marker Web UI juga akan terlihat berputar.

## Temuan dari komputer simulator

### Topic yang tersedia

Saat ROS graph aktif, topic yang ditemukan:

```text
/odom
/imu
/odometry/filtered
/scan
/map
```

### Publisher `/odom`

Publisher runtime:

```text
_Graph_ROS_Odometry_PublisherOdometry
```

Topic type:

```text
nav_msgs/msg/Odometry
```

Publisher ini berasal dari graph Isaac, bukan dari source code ROS workspace teman.

### Publisher `/imu`

Publisher runtime:

```text
_Graph_ROS_IMU_ros2_publish_imu
```

Topic type:

```text
sensor_msgs/msg/Imu
```

Sample IMU ketika robot terlihat diam:

```text
frame_id: IMU
angular_velocity.z ≈ 0.008 rad/s
linear_acceleration.x ≈ 0.109 m/s²
linear_acceleration.z ≈ 9.826 m/s²
```

Covariance pada sample IMU yang dibaca seluruhnya bernilai `0`. Ini adalah temuan yang mencurigakan dan perlu divalidasi terhadap cara graph Isaac mengisi pesan sensor.

### Publisher `/odometry/filtered`

Publisher:

```text
/ekf_filter_node
```

Sample ketika robot terlihat diam:

```text
linear.x  ≈ -0.0022 m/s
angular.z ≈ 0.011–0.013 rad/s
```

Artinya output filtered masih menunjukkan gerakan residual. Mengganti Web UI dari `/odom` ke `/odometry/filtered` saja belum terbukti menyelesaikan masalah.

## Konfigurasi aktif yang diverifikasi

Mapping launch yang aktif:

```text
amr_description/launch/amr_mapping_sim_launch.py
```

Launch tersebut memakai:

```text
amr_description/config/ekf_cfg.yaml
```

Source dan file install memiliki checksum yang sama pada saat pemeriksaan.

### EKF input aktif

Di `amr_description/config/ekf_cfg.yaml`:

```yaml
odom0: /odom
odom0_config:
  vx: true
  vyaw: true

imu0: /imu
imu0_config:
  vyaw: true
```

Dengan kata lain, EKF memfusi dua sumber yaw-rate:

```text
/odom angular.z
/imu angular_velocity.z
```

EKF juga dikonfigurasi untuk menerbitkan:

```yaml
publish_tf: true
world_frame: odom
odom_frame: odom
base_link_frame: base_link
```

### SLAM input aktif

Di `amr_description/config/slam_cfg.yaml`:

```yaml
odom_frame: odom
base_frame: base_footprint
scan_topic: /scan
use_scan_matching: true
```

SLAM bergantung pada transform odometry dan laser scan untuk membangun map.

### Navigation consumer

Di `amr_description/config/amr_cfg.yaml`, Nav2 dikonfigurasi menggunakan:

```yaml
odom_topic: /odometry/filtered
```

Ini menjelaskan mengapa `/odometry/filtered` penting untuk navigasi, tetapi tidak berarti Web UI dapat memperbaiki map hanya dengan mengganti topic grafik.

## Dugaan penyebab, berdasarkan prioritas

### Dugaan 1 — Bias angular velocity IMU

Status: **SANGAT MUNGKIN — DIDUKUNG DATA RUNTIME**

IMU masih mengirim angular velocity Z sekitar `0.008 rad/s` ketika robot terlihat diam. Karena EKF memakai `imu0_config.vyaw: true`, bias tersebut masuk ke estimasi rotasi.

### Dugaan 2 — Bias angular velocity dari `/odom`

Status: **MUNGKIN — DIDUKUNG DATA RUNTIME**

`/odom` juga sebelumnya mengirim nilai linear/angular nonzero setelah robot berhenti. Publisher-nya berasal dari graph odometry Isaac.

### Dugaan 3 — Dua sumber yaw-rate yang sama-sama bias difusikan bersamaan

Status: **MUNGKIN — DIVERIFIKASI DARI CODE**

EKF aktif menggabungkan `angular.z` dari `/odom` dan `angular_velocity.z` dari `/imu`. Jika keduanya memiliki bias, filter dapat menghasilkan `/odometry/filtered` dan TF yang tetap berputar.

### Dugaan 4 — Covariance sensor tidak representatif

Status: **MUNGKIN — DITEMUKAN PADA PESAN IMU, BELUM TERBUKTI SEBAGAI AKAR TUNGGAL**

Covariance IMU yang dibaca bernilai `0`. Arti dan penanganannya perlu dicocokkan dengan publisher Isaac dan ekspektasi `robot_localization`. Belum boleh langsung diubah tanpa pengujian.

### Dugaan 5 — Ketidaksesuaian frame `base_link` dan `base_footprint`

Status: **PERLU VERIFIKASI**

EKF memakai `base_link`, sementara SLAM memakai `base_footprint`. Ini bisa valid jika static TF `base_link → base_footprint` tersedia dan stabil. Pada pemeriksaan terakhir ketika simulator aktif, hubungan ini belum sempat divalidasi secara lengkap.

### Dugaan 6 — Visualisasi laser Web UI salah frame

Status: **MUNGKIN UNTUK VISUAL UI, BUKAN PENYEBAB UTAMA MAP SLAM**

`web-ui/src/components/MapView.vue` menghitung titik laser dari pose robot dan sudut scan, tetapi belum menerapkan transform berdasarkan `scan.header.frame_id` secara eksplisit. Ini dapat membuat titik laser merah tampak berputar atau bergeser di UI.

Namun visualisasi tersebut tidak mengubah `/map` yang dibuat `slam_toolbox`.

### Dugaan 7 — Joystick terus mengirim command setelah dilepas

Status: **SEBAGIAN BESAR TERELIMINASI**

Listener `/cmd_vel` menunjukkan command kembali ke nol setelah joystick dilepas. Masih ada potensi edge case interval bertumpuk di code joystick, tetapi belum ada bukti bahwa itu penyebab kejadian ini.

## Hal yang sudah dieliminasi

- Bukan masalah ROS_DOMAIN_ID: topic simulator terlihat pada domain yang benar.
- Bukan rosbridge tidak tersambung: `/cmd_vel` berhasil diterima ketika joystick digerakkan.
- Bukan command joystick selalu tertahan: command kembali ke nol.
- Bukan backend FastAPI: backend tidak berada di jalur realtime odometry/SLAM.
- Bukan grafik UI yang menciptakan data: grafik hanya membaca `/odom`.

## Catatan konfigurasi yang berpotensi membingungkan

Workspace teman memiliki dua file EKF berbeda:

```text
amr_bringup/config/ekf.yaml
amr_description/config/ekf_cfg.yaml
```

`amr_bringup/config/ekf.yaml` merujuk ke:

```text
/odom_raw
/imu/data_raw
```

Sedangkan mapping simulator aktif merujuk ke:

```text
/odom
/imu
```

Perbedaan ini belum diubah. Catatan ini hanya mendokumentasikan bahwa debugging harus selalu memakai konfigurasi `amr_description/config/ekf_cfg.yaml` untuk alur mapping simulator.

## Batasan pemeriksaan

Pada akhir pemeriksaan mendalam, proses Isaac masih terlihat berjalan, tetapi ROS graph sedang tidak mempublikasikan node/topic normal. Karena itu pemeriksaan TF terakhir tidak dapat diulang pada kondisi tersebut tanpa simulator mengaktifkan kembali ROS graph.

File USD Isaac berhasil diidentifikasi sebagai sumber graph sensor, tetapi environment remote tidak memiliki tooling Python USD (`pxr`) atau `usdcat` yang bisa dipakai untuk membaca isi crate USD secara terstruktur. Pemeriksaan USD yang dilakukan hanya berupa inspeksi string read-only.

## Verifikasi berikutnya yang disarankan

Tanpa mengubah konfigurasi, jalankan ketika simulator dan mapping aktif:

```bash
ros2 topic echo /cmd_vel
ros2 topic echo /odom --field twist.twist
ros2 topic echo /imu --field angular_velocity
ros2 topic echo /odometry/filtered --field twist.twist
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo base_link RPLIDAR_S2E
ros2 run tf2_ros tf2_echo odom base_footprint
```

Uji idle harus dilakukan setelah joystick tidak disentuh selama minimal 30 detik. Nilai yang dibandingkan:

```text
/cmd_vel                 harus nol setelah release
/odom                    harus mendekati nol
/imu angular velocity    harus mendekati nol
/odometry/filtered       harus mendekati nol
TF odom → base_link      harus stabil
TF base_link → laser     harus statis
```

## Rekomendasi teknis untuk fase berikutnya

1. Validasi dan perbaiki sumber bias `/imu` dan `/odom` di graph Isaac.
2. Validasi covariance IMU.
3. Evaluasi apakah EKF perlu memakai kedua sumber yaw-rate atau hanya sumber yang terbukti stabil.
4. Validasi static TF `base_link → base_footprint` dan `base_link → RPLIDAR_S2E`.
5. Setelah output EKF dan TF stabil, baru pertimbangkan mengganti grafik Web UI dari `/odom` ke `/odometry/filtered` agar konsisten dengan Nav2.
6. Jika hanya ingin memperbaiki tampilan, deadband UI boleh dipertimbangkan, tetapi tidak boleh dianggap sebagai perbaikan mapping.

## Perubahan pada sesi ini

- File baru: `docs/ODOMETRY_IMU_EKF_MAPPING_DIAGNOSTIC.md`
- File aplikasi di `web-ui/` dan `backend/`: tidak diubah.
- Simulator teman: tidak diubah.
- ROS topic, service, action, dan konfigurasi: tidak diubah.
