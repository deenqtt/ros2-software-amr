# Shared Map Storage (NFS)

## Tujuan

Menyediakan satu lokasi runtime map yang dapat dibaca dan ditulis oleh:

```text
Komputer Deden  — Web UI + Backend
Komputer teman  — ROS 2 + SLAM Toolbox + simulator
```

Kedua mesin menggunakan path runtime yang sama:

```text
/maps
```

Dengan demikian, map yang dibuat oleh SLAM Toolbox dapat langsung ditemukan
oleh Backend melalui `GET /api/maps` tanpa hard-code path workspace teman.

## Rekomendasi arsitektur

```text
Deden:/maps  ── NFS export ──>  Teman:/maps
     │                              │
     └── Backend MAPS_DIR            └── SLAM Toolbox SaveMap
```

Deden menjadi NFS server karena Backend merupakan pemilik application data.
Komputer teman menjadi NFS client dan memasang export tersebut di `/maps`.

Folder berikut tidak dipindahkan dan bukan target runtime utama:

```text
~/ros2_gprp_amr_ws/src/amr_description/map
~/ros2_gprp_amr_ws/install/amr_description/share/amr_description/map
```

Folder package tersebut tetap menjadi source/asset map simulator. Map hasil
mapping aplikasi disimpan di `/maps`.

## Konfigurasi yang digunakan

| Mesin | IP | Peran |
| --- | --- | --- |
| Deden | `192.168.2.51` | NFS server, Backend, Web UI |
| Teman | `192.168.2.133` | NFS client, ROS 2, SLAM Toolbox |

ROS service frontend tetap menggunakan:

```text
/slam_toolbox/save_map
slam_toolbox/srv/SaveMap
name: /maps/<filename>
```

## Setup Deden (NFS server)

```bash
sudo apt install nfs-kernel-server
sudo mkdir -p /maps
sudo chown deden:deden /maps
sudo chmod 775 /maps
```

Tambahkan ke `/etc/exports`:

```text
/maps 192.168.2.133(rw,sync,no_subtree_check)
```

Terapkan export:

```bash
sudo exportfs -ra
sudo systemctl enable --now nfs-kernel-server
```

Jika UFW aktif:

```bash
sudo ufw allow from 192.168.2.133 to any port 2049 proto tcp
```

## Setup komputer teman (NFS client)

Pastikan isi `/maps` telah diperiksa sebelum mount. Mount NFS akan menutupi isi
directory lokal tersebut selama mount aktif; file lokal tidak dihapus.

```bash
sudo apt install nfs-common
sudo mount -t nfs -o vers=4 192.168.2.51:/maps /maps
```

Mount permanen dapat ditambahkan ke `/etc/fstab`:

```text
192.168.2.51:/maps /maps nfs defaults,_netdev,vers=4 0 0
```

## Verifikasi

Di komputer teman:

```bash
mountpoint /maps
touch /maps/_nfs_write_test
```

Di Deden:

```bash
ls -l /maps/_nfs_write_test
```

Setelah verifikasi storage, jalankan SLAM dan pastikan:

```bash
ros2 topic info /map -v
ros2 service type /slam_toolbox/save_map
```

Kemudian Save Map dari Web UI. File `.yaml` dan `.pgm` harus terlihat di
`/maps` pada kedua mesin.

## Dampak terhadap aplikasi

- Tidak mengubah topic, service, action, atau message ROS.
- Tidak mengubah source simulator.
- Tidak memindahkan folder `amr_description/map`.
- Tidak membutuhkan path home/user teman di Web UI.
- Backend tetap menggunakan `MAPS_DIR=/maps`.
- Web UI tetap mengirim path `/maps/<filename>` ke SLAM Toolbox.

## Catatan Docker

Jika Backend dijalankan di Docker, container Backend harus melihat host
directory `/maps` melalui bind mount yang sama. Jika Backend dijalankan lokal
dengan Python, `MAPS_DIR=/maps` langsung menunjuk ke NFS server directory.

Pada repository ini, `docker-compose.yml` saat ini menggunakan:

```text
./maps:/maps
```

Jadi mode Docker masih memakai directory `maps` relatif terhadap repository,
bukan host directory `/maps` yang diekspor NFS. Konfigurasi Docker belum
diubah pada sesi ini. Shared storage yang diterapkan sudah sesuai untuk mode
Backend lokal/Uvicorn dengan `MAPS_DIR=/maps`; jika nanti memakai Docker,
bind mount Docker perlu diarahkan ke storage yang sama sebagai pekerjaan
terpisah.

## Rollback mount client

Untuk melepas mount di komputer teman:

```bash
sudo umount /maps
```

Hapus baris `/etc/fstab` jika sebelumnya ditambahkan. Rollback ini tidak
menghapus file pada NFS server maupun folder lokal yang sebelumnya tertutup
oleh mount.

## Status penerapan

Status: **AKTIF dan terverifikasi** pada 2026-09-18.

### Deden (`192.168.2.51`)

- Paket `nfs-kernel-server` dan dependensinya terpasang.
- Directory `/maps` dibuat dengan owner `deden:deden` dan mode `775`.
- Export aktif:

  ```text
  /maps 192.168.2.133(rw,sync,no_subtree_check)
  ```

- Service `nfs-server` aktif.
- UFW Deden saat verifikasi berstatus inactive.

### Komputer teman (`192.168.2.133`)

- Paket `nfs-common` dan dependensinya terpasang.
- `/maps` berhasil di-mount dari:

  ```text
  192.168.2.51:/maps
  ```

- Mount persisten ditambahkan ke `/etc/fstab`:

  ```text
  192.168.2.51:/maps /maps nfs defaults,_netdev,vers=4 0 0
  ```

- Write test dari komputer teman terlihat di Deden melalui `/maps`.
- File write test kemudian dihapus; tidak ada file map pengguna yang dihapus.
- Backend `127.0.0.1:3001` tidak sedang berjalan saat verifikasi endpoint,
  sehingga `GET /api/maps` belum diuji runtime pada sesi ini.

Source code Web UI/backend dan source simulator tidak diubah oleh setup NFS.
