#!/usr/bin/env bash
# ===================================================================
#  FleetPanel — LAN-ONLY setup for a Banana Pi (Armbian/Debian)
#
#  Use this when ALL managed PCs are on the SAME local network as the
#  Pi. No DuckDNS, no Cloudflare, no Tailscale, no router forwarding,
#  no HTTPS certificates needed — PCs reach the panel directly at
#  http://<PI-LAN-IP>:8090.
#
#  Runs ALONGSIDE your existing slideshow (port 5000) untouched.
#  Tuned for a low-RAM board (1 worker + threads, 200 MB cap, swap).
#
#  Usage:
#     sudo ./setup-pi-lan.sh
# ===================================================================
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Please run with sudo/root."; exit 1; fi

APP_DIR="/opt/fleetpanel"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)/server"
PORT=8090

# detect the Pi's primary LAN IP for the final instructions
LAN_IP="$(hostname -I | awk '{print $1}')"

echo "[0/5] Ensuring swap exists (helps a tight-RAM board)..."
if [[ "$(swapon --show --noheadings | wc -l)" -eq 0 ]]; then
  fallocate -l 1G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=1024
  chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "  1G swap enabled."
else
  echo "  Swap already present."
fi

echo "[1/5] Installing packages (minimal — no nginx/certbot needed)..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip curl ca-certificates

echo "[2/5] Installing/updating FleetPanel code in $APP_DIR (keeping your data)..."
mkdir -p "$APP_DIR/server"
# Copy the CODE only; never overwrite the database, user data, or secrets.
# --exclude keeps fleet.db / userdata / .env intact across re-runs.
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude 'fleet.db' --exclude 'userdata/' --exclude '.env' \
        "$SRC_DIR/" "$APP_DIR/server/"
else
  # rsync not present: copy code files but explicitly preserve data files.
  cp -r "$SRC_DIR/." "$APP_DIR/server/.__new" 2>/dev/null || true
  rm -f "$APP_DIR/server/.__new/fleet.db" 2>/dev/null || true
  rm -rf "$APP_DIR/server/.__new/userdata" 2>/dev/null || true
  cp -r "$APP_DIR/server/.__new/." "$APP_DIR/server/"
  rm -rf "$APP_DIR/server/.__new"
fi
cd "$APP_DIR/server"
python3 -m venv .venv 2>/dev/null || true
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt

echo "[3/5] Configuring secrets (preserving existing so users/token survive)..."
if [[ -f "$APP_DIR/server/.env" ]]; then
  echo "  Existing .env found — keeping current secrets, DB, and users."
else
  SECRET="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
  ENROLL="$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')"
  cat > "$APP_DIR/server/.env" <<EOF
FLEET_SECRET=$SECRET
FLEET_ENROLL_SECRET=$ENROLL
FLEET_DB=$APP_DIR/server/fleet.db
FLEET_DATA=$APP_DIR/server/userdata
EOF
  chmod 600 "$APP_DIR/server/.env"
  echo "  New .env created (first install)."
fi

echo "[4/5] Creating systemd service (binds to ALL interfaces on :$PORT)..."
# 0.0.0.0 so any PC on the LAN can reach it. Low-memory gunicorn tuning.
cat > /etc/systemd/system/fleetpanel.service <<EOF
[Unit]
Description=FleetPanel (LAN mode)
After=network.target

[Service]
WorkingDirectory=$APP_DIR/server
EnvironmentFile=$APP_DIR/server/.env
ExecStart=$APP_DIR/server/.venv/bin/gunicorn --workers 1 --threads 4 \\
    --preload --max-requests 500 --max-requests-jitter 50 \\
    -b 0.0.0.0:$PORT app:app
Restart=always
MemoryMax=200M
Nice=5
User=www-data

[Install]
WantedBy=multi-user.target
EOF
id www-data >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin www-data
chown -R www-data:www-data "$APP_DIR"
systemctl daemon-reload
systemctl enable fleetpanel
systemctl restart fleetpanel   # restart so updated code loads (safe on re-runs)
sleep 2

# Read the ACTUAL current enrollment secret from .env (works on first install
# and on re-runs where we preserved the existing one).
ENROLL="$(grep '^FLEET_ENROLL_SECRET=' "$APP_DIR/server/.env" | cut -d= -f2-)"

echo "[5/5] Checking service..."
if systemctl is-active --quiet fleetpanel; then
  echo "  FleetPanel is running on 0.0.0.0:$PORT"
else
  echo "  [WARN] not active; check: journalctl -u fleetpanel -n 40"
fi

echo ""
echo "======================================================================"
echo " FleetPanel is LIVE on your local network:"
echo ""
echo "     http://${LAN_IP}:${PORT}"
echo ""
echo " (Your slideshow on port 5000 was NOT touched.)"
echo ""
echo " Agent ENROLLMENT SECRET (use it in setup-agent.bat):"
echo "     $ENROLL"
echo ""
echo " Admin login: username 'admin'. One-time password:"
echo "     journalctl -u fleetpanel | grep -A2 'INITIAL ADMIN'"
echo " Open the URL above in a browser, log in, and change the password."
echo ""
echo " On each Windows PC (as Administrator):"
echo "     setup-agent.bat http://${LAN_IP}:${PORT}  $ENROLL"
echo "======================================================================"
echo ""
echo " TIP: give the Pi a STATIC/reserved IP in your router so ${LAN_IP}"
echo "      never changes (otherwise agents lose the panel after a reboot)."
