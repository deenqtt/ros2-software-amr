# Laporan Progress — amr Web UI

**Tanggal:** 06 April 2026
**Developer:** Software Team (Bagian Web UI & Simulasi)

---

## Ringkasan

Web UI berbasis browser untuk monitoring dan kontrol robot AGV secara realtime.
Terhubung ke robot via WebSocket (rosbridge). Semua fitur sudah berjalan di simulasi.

---

## Fitur yang Sudah Selesai

### 🗺️ Map & Visualisasi

- Peta occupancy grid tampil realtime dari robot
- Posisi robot (marker + footprint sesuai ukuran robot) terpantau di peta
- Path navigasi yang direncanakan Nav2 tampil di peta
- Overlay costmap (area terlarang Nav2) bisa toggle on/off
- Partikel AMCL tampil untuk indikasi akurasi lokalisasi
- Visualisasi laser scan (titik-titik jangkauan sensor)

### 🕹️ Mode Klik Peta

Pengguna bisa ganti mode klik peta:

| Mode           | Fungsi                                        |
| -------------- | --------------------------------------------- |
| Navigate       | Klik peta → robot langsung jalan ke titik itu |
| Waypoint       | Klik peta → tambah ke daftar waypoint mission |
| Initial Pose   | Klik + drag → set posisi awal robot di AMCL   |
| Destination    | Klik peta → tambah destination point baru     |
| Dock Placement | Klik peta → tambah dock station baru          |
| Keepout        | Gambar polygon → area terlarang untuk robot   |

### 🧭 Navigasi Single Point

- Input koordinat manual (x, y, sudut) atau klik peta
- Tombol Cancel untuk hentikan navigasi
- Tampil status: idle / navigating

### 📋 Mission System

- Buat daftar destination point di peta (Pick / Drop / Pick&Drop)
- Tambah waypoint dari destination (maks 5 titik per misi)
- Tiap waypoint bisa diset:
  - **Task**: Pick atau Drop
  - **Mode**: Auto (langsung lanjut) atau Manual (tunggu konfirmasi operator)
- Jalankan misi → robot eksekusi satu per satu otomatis
- **Loop**: misi bisa diulang N kali atau terus-menerus (0 = ∞)
- **Timeout watchdog**: auto-lanjut jika robot stuck > N detik (default 120s)
- Tombol **Confirm** muncul di UI saat robot menunggu konfirmasi Manual mode
- Tombol Pause / Stop kapan saja
- Progress bar waypoint saat misi berjalan
- Save dan load misi tersimpan (per map)

### ⚡ Docking

- Daftar dock station bisa ditambah, rename, hapus
- Posisi dock + approach point bisa diset langsung dari peta
- Tombol **Send to Dock** → robot navigasi otomatis ke dock
- Proses docking: navigasi ke titik approach → mundur masuk dock
- Tombol Undock → robot keluar dari dock
- Status docking tampil realtime (idle / navigating / docked / undocking / error)
- **Auto-dock**: bisa diaktifkan, robot otomatis ke dock jika baterai rendah (threshold bisa diset)

### 🎮 Teleop Manual

- Joystick pad di UI (drag untuk kontrol arah)
- D-pad tombol (atas/bawah/kiri/kanan)
- Preset kecepatan: Slow / Normal / Fast
- Tombol stop darurat

### 🗺️ SLAM & Mapping

- Bisa ganti mode: SLAM (mapping) atau Navigation (pakai map yang sudah ada)
- Save map langsung dari UI (tersimpan ke server)
- Load map yang sudah tersimpan

### 🚧 Keepout Zones

- Gambar polygon di peta → area yang tidak boleh dilalui robot
- Bisa hapus zona per zona atau clear semua
- Zona dikirim ke Nav2 costmap filter secara realtime
- Tersimpan di database, restore otomatis saat reconnect

### 🔋 Monitoring

- Status koneksi ROS (connected / disconnected), tombol connect/disconnect
- Posisi robot realtime (x, y, sudut)
- Kecepatan linear dan angular
- Baterai: persentase + indikator charging
- Status navigasi aktif

### 🗂️ Manajemen Map & Data

- Upload map baru (file `.yaml` + `.pgm`) via drag & drop atau file picker
- Aktivasi map → semua data (destination, dock, misi) otomatis filter per map
- CRUD destination point: tambah, rename, ubah type, hapus
- CRUD dock station: tambah dari peta, rename, set approach point, hapus

### 📷 Camera Feed

- Tampil stream kamera robot langsung di UI
- Toggle show/hide

---

## Status Integrasi Robot Asli

| Item                         | Status           | Catatan                          |
| ---------------------------- | ---------------- | -------------------------------- |
| Koneksi WebSocket            | ✅ Terkonfirmasi | Rosbridge :8765 aktif di robot   |
| `/mission_plan` action       | ✅ Terkonfirmasi | Action server ada di robot       |
| `/station_config` service    | ✅ Terkonfirmasi | Bisa dipanggil dari UI           |
| `/dock_command` service      | ✅ Terkonfirmasi | Bisa dipanggil dari UI           |
| Nodes stabil running         | ⚠️ Belum stabil  | Nodes di robot kadang naik turun |
| Test misi full di robot asli | 🔄 Belum         | Tunggu robot side stabil         |

---

## Yang Masih Open

| #   | Item                                                |
| --- | --------------------------------------------------- |
| 1   | Manual mode belum ada batas waktu tunggu konfirmasi |
| 2   | Test misi loop di robot asli (simulasi sudah OK)    |
| 3   | Progress bar persentase off by one                  |

---

## Stack

| Bagian         | Teknologi                            |
| -------------- | ------------------------------------ |
| Simulasi       | ROS2 Humble + Gazebo + Nav2 (Docker) |
| Web UI         | Vue 3 + Pinia + Leaflet + roslibjs   |
| Backend        | FastAPI + SQLite                     |
| Komunikasi ROS | rosbridge WebSocket :8765            |
| Backend API    | HTTP REST :3001                      |
