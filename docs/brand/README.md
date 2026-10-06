# Brand

| Folder | Isi |
|---|---|
| `amr-control/` | Logo produk AMR Control (SVG) |
| `gspe/` | Logo PT Graha Sumber Prima Elektronik (dipakai di panduan PDF) |

Desain AMR Control juga ada di Figma: [AMR Control — Logo](https://www.figma.com/design/MkdGLhzpcZnQ34bWcbLY4G).

## AMR Control

Warna mengikuti design system Web UI ([`../design/DESIGN.md`](../design/DESIGN.md)):
primary `#0052FF`, ink `#0A0B0D`, putih. Semua ikon 128 × 128, sudut 28.

| File | Konsep | Makna |
|---|---|---|
| `concept-b-route.svg` | **Route-A (rekomendasi)** | Huruf A dibentuk dari rute: dua kaki adalah jalur antar stasiun, puncaknya tujuan, palang putus-putus jalur yang direncanakan Nav2. AMR yang menjalankan misi dari titik ke titik. Paling khas, tetap terbaca di 16 px. |
| `concept-a-pose.svg` | Pose | Penanda robot persis seperti di peta aplikasi: titik dengan garis arah, cincin lokalisasi, jejak di belakang. Robot tahu di mana ia berada dan ke mana menuju. Cocok untuk favicon dan ikon aplikasi. |
| `concept-c-grid.svg` | Grid | Peta occupancy SLAM (sel terisi = dinding) dengan robot dan sapuan lidar. Memetakan lalu bernavigasi di peta itu. Varian gelap. |
| `lockup-route.svg` | Lockup | Ikon Route-A dengan tulisan "AMR Control" (huruf sudah berupa outline, tidak butuh font Inter). |

Belum dipasang di aplikasi (favicon, sidebar, kiosk). Pilih satu konsep dulu.
