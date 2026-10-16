# Status Rekomendasi — Riset MiR untuk AMR Control

Sumber: [`Riset-MiR-untuk-AMR-Control.pdf`](./Riset-MiR-untuk-AMR-Control.pdf), Bab 12
"Rekomendasi" (halaman 8). Dokumen ini memetakan setiap rekomendasi ke kondisi
kode pada 16 Oktober 2026, siapa pemiliknya (sisi web: frontend/backend/agent
vs. sisi robot: `master_control`, repo tim robot), dan usulan urutan kerja.

## Ringkasan status

| # | Rekomendasi | Status | Pemilik utama |
|---|-------------|--------|----------------|
| 1 | Pick/drop dengan docking (entry → dock → aksi → confirm → undock) | ✅ Selesai | sisi robot + agent (jalur `mission_plan`) |
| 2 | Status robot terpadu + tombol Pause/Continue/Reset | 🟡 Sebagian | web (backend, UI, kiosk) |
| 3 | Antrean misi dengan auto-dispatch | ❌ Belum ada | web (backend + UI) |
| 4 | Try/Catch dan Prompt user dengan timeout sebagai jenis step | 🟡 Sebagian | web + sisi robot |
| 5 | Kunci station/dock satu robot (aturan 10 m/1 m) + zona Limit-robots | ❌ Belum ada | web (backend) + zona (agent) |
| 6 | Charging otomatis dengan ambang baterai | 🟡 Menunggu hardware | sisi robot (charger fisik) + web (kebijakan) |
| 7 | Keselamatan robot asli (scanner safety, STO, e-stop, watchdog, rem) | ❌ Belum ada | tim robot (hardware) + web (watchdog software) |
| 8 | Zona Directional & Critical + webhook integrasi pabrik | 🟡 Sebagian (keepout ada) | web + agent |

Legenda: ✅ jalan · 🟡 sebagian / tertahan · ❌ belum dimulai.

## Detail per poin

### 1. Pick/Drop dengan docking — ✅ selesai

Alur MiR (entry position → docking → aksi → konfirmasi → undocking) sudah jalan
lewat `mission_plan` ke `master_control`, yang memanggil Nav2 `opennav_docking`:

- Robot menuju *staging pose* 1,0 m di belakang station
  (`staging_x_offset: -1.0`) dengan badan **menghadap menjauh** dari station
  (`staging_yaw_offset ≈ π`), lalu **mundur** masuk (`dock_backwards: true`) —
  rear-first, sesuai posisi kontak charger.
- Konfigurasi live: `amr_description/config/amr_cfg.yaml` (sim) dan
  `amr_bringup/config/amr_param.yaml` (robot fisik).
- Catatan Oktober 2026: model staging di UI stasiun pernah terbalik (dianggap
  maju); sudah diperbaiki di `new_webui/frontend/src/domain/docking.ts`
  (`stagingPose()` kini `yaw + π`) plus panah arah hadap di gambar docking entry.

### 2. Status robot terpadu + Pause/Continue/Reset — 🟡 sebagian

- Yang sudah ada: state robot tersebar di dashboard, detail robot, dan kiosk;
  master_control punya handler `robot_mode`; kiosk punya layar status.
- Yang kurang: satu daftar state dengan warna baku yang sama di ketiga tempat;
  tombol Pause/Continue/Reset; error menunggu Reset operator (tidak dicoba
  ulang diam-diam).
- Bisa dikerjakan penuh oleh sisi web.

### 3. Antrean misi dengan auto-dispatch — ❌ belum

- Saat ini run di-start manual per robot dari UI.
- Yang dibutuhkan: tabel antrean berprioritas di backend, pemilih robot
  (terdekat yang kosong dengan baterai cukup), dan penugasan manual tetap
  tersedia sebagai override.
- Fitur terbesar di sisi web; sebaiknya setelah poin 5 (locking) beres.

### 4. Try/Catch dan Prompt user dengan timeout — 🟡 sebagian

- Yang sudah ada: verification gate (WAITING_VERIFICATION → konfirmasi
  operator) dan `MISSION_STEP_TIMEOUT_S` di agent.
- Yang kurang: timeout pada prompt konfirmasi, dan jenis step baru
  try/catch (cabang error per step). Skema misi + editor UI + agent perlu
  diubah; perilaku step di `master_control` mungkin perlu tim robot.

### 5. Kunci station/dock (10 m/1 m) + zona Limit-robots — ❌ belum

- Dua robot saat ini bisa menyasar station yang sama bersamaan.
- Yang dibutuhkan: kunci resource per station/dock di backend selama sebuah run
  aktif (aturan 10 m/1 m), disusul tipe zona Limit-robots di editor zona +
  `zone_mask_server`/`zone_raster` di agent.

### 6. Charging otomatis — 🟡 tertahan hardware

- master_control sudah punya jalur low-battery docking
  (`LOW_BATTERY_DOCK_STARTED`).
- Sisanya menunggu charger fisik tersedia; kebijakan ambang baterai dan
  prioritas darurat bisa disiapkan di sisi web setelahnya.

### 7. Keselamatan robot asli — ❌ belum (kritis untuk operasi lantai)

- Hardware (scanner safety, STO, e-stop, tes rem, checklist commissioning):
  ranah tim robot.
- Watchdog software yang menghentikan robot saat agent/koneksi mati: bisa
  dimulai oleh sisi web (agent heartbeat) bekerja sama dengan tim robot.

### 8. Zona Directional & Critical + webhook — 🟡 sebagian

- Zona keepout sudah ada (costmap filter). Directional (searah) dan Critical
  (perlambat/berhenti) belum; webhook untuk integrasi pabrik belum.
- Ditambah satu item "perlu dicek" dari dokumen: apakah keepout zone ikut
  menahan robot saat teleop manual — belum pernah dites.

## Usulan urutan kerja (sisi web)

1. **Poin 2** — status terpadu + Pause/Continue/Reset: dampak UX tercepat,
   effort kecil–sedang, penuh di tangan sisi web.
2. **Poin 5** — locking station/dock (10 m/1 m): fondasi multi-robot sebelum
   antrean.
3. **Poin 3** — antrean + auto-dispatch: fitur terbesar, setelah locking.
4. **Poin 8** — zona directional/critical + webhook (+ tes keepout vs teleop).
5. **Poin 4** — prompt timeout + try/catch.
6. **Poin 6 & 7** — mengikuti kesiapan hardware (charger) dan tim robot.

## Perlu dicek

- [ ] Apakah keepout zone menahan robot saat dikemudikan manual (teleop)?
      Tes cepat di Isaac Sim; dokumen MiR tidak konsisten soal ini dan di
      AMR Control belum pernah dites.
