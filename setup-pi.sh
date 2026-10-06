#!/usr/bin/env bash
# ===================================================================
#  FleetPanel — OPTIMISED setup for a Banana Pi / low-RAM ARM board
#  (Armbian / Debian). Designed to run ALONGSIDE an existing service
#  (e.g. a slideshow web app on port 5000) WITHOUT disturbing it.
#
#  Differences vs setup-server.sh (which targets a full VM):
#    * Tuned for ~512 MB RAM: 1 gunicorn worker, threaded, preloaded.
#    * Uses port 8090 internally (leaves your :5000 slideshow alone).
#    * Does NOT touch/remove other nginx sites.
#    * Ensures a swap file exists (protects a tight-RAM board).
#    * Supports TWO ways to reach it from the internet:
#         --cloudflared  (recommended for home networks: no port-forward,
#                         free HTTPS, nothing exposed on your home IP)
#         --duckdns      (classic: needs router port-forward 80/443)
#
#  Usage:
#    Cloudflare Tunnel (recommended, behind a home router):
#       sudo ./setup-pi.sh --cloudflared
#    DuckDNS + your own port-forwarding:
#       sudo ./setup-pi.sh --duckdns fleetpanel.duckdns.org <TOKEN> fleetpanel
# ===================================================================
set -euo pipefail

MODE="${1:-}"
if [[ "$MODE" != "--cloudflared" && "$MODE" != "--duckdns" ]]; then
  echo "Usage:"
  echo "  sudo ./setup-pi.sh --cloudflared"
  echo "  sudo ./setup-pi.sh --duckdns <domain> <token> <subdomain>"
  exit 1
fi
if [[ $EUID -ne 0 ]]; then echo "Please run with sudo/root."; exit 1; fi

APP_DIR="/opt/fleetpanel"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)/server"
PORT=8090   # internal port; your slideshow keeps :5000

# ---------------------------------------------------------------- 0. swap check
echo "[0/6] Checking swap (tight-RAM boards benefit from a swap file)..."
if [[ "$(swapon --show --noheadings | wc -l)" -eq 0 ]]; then
  echo "  No swap found. Creating a 1G swap file..."
  fallocate -l 1G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=1024
  chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "  1G swap enabled."
else
  echo "  Swap already present. Good."
fi

# --------------------------------------------------------------- 1. packages
echo "[1/6] Installing packages (minimal)..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip curl ca-certificates

# ------------------------------------------------------------------ 2. app
echo "[2/6] Installing FleetPanel to $APP_DIR..."
mkdir -p "$APP_DIR/server"
cp -r "$SRC_DIR/." "$APP_DIR/server/"
cd "$APP_DIR/server"
python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt

# --------------------------------------------------------------- 3. secrets
echo "[3/6] Generating secrets..."
SECRET="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
ENROLL="$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')"
cat > "$APP_DIR/server/.env" <<EOF
FLEET_SECRET=$SECRET
FLEET_ENROLL_SECRET=$ENROLL
FLEET_DB=$APP_DIR/server/fleet.db
FLEET_DATA=$APP_DIR/server/userdata
EOF
chmod 600 "$APP_DIR/server/.env"

# ---------------------------------------------------------- 4. systemd service
# 1 worker + 4 threads + preload = low, stable memory footprint on the Pi.
echo "[4/6] Creating low-memory systemd service on port $PORT..."
cat > /etc/systemd/system/fleetpanel.service <<EOF
[Unit]
Description=FleetPanel (Banana Pi)
After=network.target

[Service]
WorkingDirectory=$APP_DIR/server
EnvironmentFile=$APP_DIR/server/.env
ExecStart=$APP_DIR/server/.venv/bin/gunicorn --workers 1 --threads 4 \\
    --preload --max-requests 500 --max-requests-jitter 50 \\
    -b 127.0.0.1:$PORT app:app
Restart=always
# Keep FleetPanel from starving the slideshow: cap memory & be low priority.
MemoryMax=200M
Nice=5
User=www-data

[Install]
WantedBy=multi-user.target
EOF
id www-data >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin www-data
chown -R www-data:www-data "$APP_DIR"
systemctl daemon-reload
systemctl enable --now fleetpanel
sleep 2
if systemctl is-active --quiet fleetpanel; then
  echo "  FleetPanel running on 127.0.0.1:$PORT"
else
  echo "  [WARN] service not active; check: journalctl -u fleetpanel -n 40"
fi

# ---------------------------------------------------------- 5. expose it
if [[ "$MODE" == "--cloudflared" ]]; then
  echo "[5/6] Installing cloudflared (free tunnel, no port-forwarding)..."
  ARCH="$(dpkg --print-architecture)"   # armhf / arm64
  CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}"
  curl -fsSL "$CF_URL" -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared
  echo ""
  echo "  cloudflared installed. Finish the tunnel interactively:"
  echo "    1) cloudflared tunnel login          # opens a browser link; pick your domain"
  echo "    2) cloudflared tunnel create fleetpanel"
  echo "    3) Route your hostname to the local service on port $PORT:"
  echo "         cloudflared tunnel route dns fleetpanel panel.yourdomain.com"
  echo "    4) Run it as a service pointing at http://127.0.0.1:$PORT"
  echo "         (see docs/PI-SETUP.md for the exact config.yml)"
  echo ""
  echo "  NOTE: A Cloudflare tunnel needs a domain on a Cloudflare account."
  echo "  If you only have DuckDNS, re-run with --duckdns instead."
else
  DOMAIN="${2:-}"; TOKEN="${3:-}"; SUB="${4:-}"
  if [[ -z "$DOMAIN" || -z "$TOKEN" || -z "$SUB" ]]; then
    echo "  --duckdns needs: <domain> <token> <subdomain>"; exit 1
  fi
  echo "[5/6] Setting up nginx (dedicated site) + DuckDNS for $DOMAIN..."
  apt-get install -y nginx certbot python3-certbot-nginx
  cat > /etc/nginx/sites-available/fleetpanel <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 200M;
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
  # Enable ONLY our site; do NOT remove others (your slideshow stays intact).
  ln -sf /etc/nginx/sites-available/fleetpanel /etc/nginx/sites-enabled/fleetpanel
  nginx -t && systemctl reload nginx

  # DuckDNS updater
  cat > /usr/local/bin/duckdns.sh <<EOF
#!/usr/bin/env bash
curl -k -s "https://www.duckdns.org/update?domains=$SUB&token=$TOKEN&ip=" >> /var/log/duckdns.log
EOF
  chmod +x /usr/local/bin/duckdns.sh
  ( crontab -l 2>/dev/null | grep -v duckdns.sh; echo "*/5 * * * * /usr/local/bin/duckdns.sh" ) | crontab -
  /usr/local/bin/duckdns.sh || true

  echo "  DuckDNS updated. NOW forward ports 80 and 443 on your router to this Pi,"
  echo "  then get HTTPS with:  certbot --nginx -d $DOMAIN"
fi

# ------------------------------------------------------------------- 6. done
echo ""
echo "======================================================================"
echo " FleetPanel installed on your Banana Pi (internal port $PORT)."
echo " Your slideshow on port 5000 was NOT touched."
echo ""
echo " Agent ENROLLMENT SECRET (use in setup-agent.bat):"
echo "     $ENROLL"
echo ""
echo " Admin login: username 'admin'. One-time password:"
echo "     journalctl -u fleetpanel | grep -A2 'INITIAL ADMIN'"
echo " Log in and change it immediately."
echo "======================================================================"
