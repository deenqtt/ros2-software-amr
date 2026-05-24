#!/usr/bin/env bash
# =============================================================================
# deploy_jetson.sh — Setup + deploy AMR software di Jetson
#
# Jalankan di Jetson sebagai root:
#   sudo /opt/amr/deploy_jetson.sh
#
# Yang dilakukan script ini:
#   1. Install nginx + python3-venv (apt)
#   2. Buat Python venv + install backend dependencies
#   3. Buat systemd service: amr-backend (uvicorn port 3001)
#   4. Konfigurasi nginx: serve web-ui dist di port 80
#   5. Start semua service
# =============================================================================
set -euo pipefail

# ── Konfigurasi ──────────────────────────────────────────────────────────────
AMR_DIR="/opt/amr"
BACKEND_DIR="$AMR_DIR/backend"
WEBUI_DIR="$AMR_DIR/web-ui/dist"
MAPS_DIR="$AMR_DIR/maps"
DATA_DIR="$AMR_DIR/data"
VENV_DIR="$AMR_DIR/venv"

BACKEND_PORT=3001
NGINX_PORT=80

# ROS maps path: path yang dipakai ROS/Nav2 untuk load map
# Harus sama dengan path yang di-mount di ROS container / dikonfigurasi di Nav2
ROS_MAPS_PATH="${ROS_MAPS_PATH:-$MAPS_DIR}"

# User yang akan menjalankan backend service (bukan root)
# Jika di-sudo, pakai $SUDO_USER; fallback ke 'amr'
SERVICE_USER="${SUDO_USER:-amr}"

NGINX_CONF="/etc/nginx/sites-available/amr"
BACKEND_SERVICE="/etc/systemd/system/amr-backend.service"

# ── Guard: harus root ────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  echo "ERROR: Script ini harus dijalankan sebagai root."
  echo "  Gunakan: sudo $0"
  exit 1
fi

echo "======================================================"
echo " AMR Jetson Deployment"
echo " AMR dir  : $AMR_DIR"
echo " Backend  : $BACKEND_DIR  (port $BACKEND_PORT)"
echo " Web UI   : $WEBUI_DIR    (nginx port $NGINX_PORT)"
echo " Maps dir : $MAPS_DIR"
echo " Service user: $SERVICE_USER"
echo "======================================================"
echo ""

# ── 1. System dependencies ───────────────────────────────────────────────────
echo "[1/6] Menginstall system dependencies..."
apt-get update -q
apt-get install -y -q nginx python3-pip python3-venv
echo "  → nginx, python3-pip, python3-venv: OK"

# ── 2. Python virtual environment ────────────────────────────────────────────
echo ""
echo "[2/6] Menyiapkan Python virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$BACKEND_DIR/requirements.txt" -q
echo "  → venv: $VENV_DIR"
echo "  → dependencies installed"

# ── 3. Direktori data + permissions ──────────────────────────────────────────
echo ""
echo "[3/6] Menyiapkan direktori data..."
mkdir -p "$MAPS_DIR" "$DATA_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$AMR_DIR" 2>/dev/null || true
echo "  → $MAPS_DIR"
echo "  → $DATA_DIR"

# ── 4. Systemd service: amr-backend ──────────────────────────────────────────
echo ""
echo "[4/6] Membuat systemd service: amr-backend..."

cat > "$BACKEND_SERVICE" <<EOF
[Unit]
Description=AMR FastAPI Backend
After=network.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BACKEND_DIR
Environment=MAPS_DIR=$MAPS_DIR
Environment=DB_PATH=$DATA_DIR/amr.db
Environment=ROS_MAPS_PATH=$ROS_MAPS_PATH

ExecStart=$VENV_DIR/bin/uvicorn main:app \\
    --host 0.0.0.0 \\
    --port $BACKEND_PORT \\
    --workers 1 \\
    --log-level info

Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable amr-backend
systemctl restart amr-backend
echo "  → amr-backend.service: enabled + started"

# ── 5. Nginx configuration ────────────────────────────────────────────────────
echo ""
echo "[5/6] Mengkonfigurasi nginx..."

cat > "$NGINX_CONF" <<EOF
server {
    listen $NGINX_PORT default_server;
    listen [::]:$NGINX_PORT default_server;
    server_name _;

    # Serve Vue SPA dari web-ui/dist
    root $WEBUI_DIR;
    index index.html;

    # Vue Router: semua unknown path fallback ke index.html (SPA)
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Gzip compression untuk performa
    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;
}
EOF

# Aktifkan site AMR, nonaktifkan default nginx
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/amr
rm -f /etc/nginx/sites-enabled/default

# Test konfigurasi nginx sebelum restart
nginx -t
systemctl restart nginx
systemctl enable nginx
echo "  → nginx: configured + restarted"
echo "  → site: /etc/nginx/sites-enabled/amr"

# ── 6. Status check ───────────────────────────────────────────────────────────
echo ""
echo "[6/6] Memeriksa status services..."
sleep 3

BACKEND_OK=false
NGINX_OK=false

systemctl is-active --quiet amr-backend && BACKEND_OK=true || true
systemctl is-active --quiet nginx       && NGINX_OK=true  || true

if $BACKEND_OK; then
  echo "  ✓ amr-backend : running (port $BACKEND_PORT)"
else
  echo "  ✗ amr-backend : FAILED"
  echo "    Cek log: journalctl -u amr-backend -n 30"
fi

if $NGINX_OK; then
  echo "  ✓ nginx       : running (port $NGINX_PORT)"
else
  echo "  ✗ nginx       : FAILED"
  echo "    Cek log: journalctl -u nginx -n 30"
fi

# Ambil IP Jetson
JETSON_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "======================================================"
echo " Deployment selesai!"
echo ""
echo "  Web UI   : http://$JETSON_IP"
echo "  API      : http://$JETSON_IP:$BACKEND_PORT/api"
echo "  Maps dir : $MAPS_DIR"
echo ""
echo " Upload map via UI: http://$JETSON_IP → Maps panel"
echo ""
echo " Useful commands:"
echo "   journalctl -u amr-backend -f   # log backend"
echo "   systemctl restart amr-backend  # restart backend"
echo "   systemctl restart nginx        # restart nginx"
echo "======================================================"
