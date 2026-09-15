#!/usr/bin/env bash
# ===================================================================
#  FleetPanel Server setup (run on your always-on Linux VM)
#  Works on Ubuntu/Debian (Google Cloud e2-micro, a VPS, Oracle, etc.)
#
#  What it does:
#    1. Installs Python, nginx, certbot
#    2. Installs FleetPanel into /opt/fleetpanel with a virtualenv
#    3. Generates stable secrets (session + enrollment)
#    4. Runs it under gunicorn via systemd (auto-restart, starts on boot)
#    5. Configures nginx reverse proxy + HTTPS (Let's Encrypt) for your domain
#    6. Installs the DuckDNS cron updater
#
#  Usage (as root or with sudo):
#    sudo ./setup-server.sh yourname.duckdns.org  DUCKDNS_TOKEN  DUCKDNS_SUBDOMAIN
#  Example:
#    sudo ./setup-server.sh mypanel.duckdns.org  abcd-1234  mypanel
# ===================================================================
set -euo pipefail

DOMAIN="${1:-}"
DUCK_TOKEN="${2:-}"
DUCK_SUB="${3:-}"

if [[ -z "$DOMAIN" ]]; then
  echo "Usage: sudo ./setup-server.sh <domain> [duckdns_token] [duckdns_subdomain]"
  echo "Example: sudo ./setup-server.sh mypanel.duckdns.org abcd-1234 mypanel"
  exit 1
fi
if [[ $EUID -ne 0 ]]; then echo "Please run with sudo/root."; exit 1; fi

APP_DIR="/opt/fleetpanel"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)/server"

echo "[1/6] Installing packages..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx curl

echo "[2/6] Installing app to $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r "$SRC_DIR/." "$APP_DIR/server/" 2>/dev/null || { mkdir -p "$APP_DIR/server"; cp -r "$SRC_DIR/." "$APP_DIR/server/"; }
cd "$APP_DIR/server"
python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt

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

echo "[4/6] Creating systemd service..."
cat > /etc/systemd/system/fleetpanel.service <<EOF
[Unit]
Description=FleetPanel
After=network.target

[Service]
WorkingDirectory=$APP_DIR/server
EnvironmentFile=$APP_DIR/server/.env
ExecStart=$APP_DIR/server/.venv/bin/gunicorn -w 3 -b 127.0.0.1:8080 app:app
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
EOF
chown -R www-data:www-data "$APP_DIR"
systemctl daemon-reload
systemctl enable --now fleetpanel
sleep 2

echo "[5/6] Configuring nginx + HTTPS for $DOMAIN..."
cat > /etc/nginx/sites-available/fleetpanel <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 200M;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/fleetpanel /etc/nginx/sites-enabled/fleetpanel
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect || \
  echo "[WARN] certbot failed - run 'certbot --nginx -d $DOMAIN' manually once DNS resolves."

echo "[6/6] DuckDNS updater..."
if [[ -n "$DUCK_TOKEN" && -n "$DUCK_SUB" ]]; then
  cat > /usr/local/bin/duckdns.sh <<EOF
#!/usr/bin/env bash
curl -k -s "https://www.duckdns.org/update?domains=$DUCK_SUB&token=$DUCK_TOKEN&ip=" >> /var/log/duckdns.log
EOF
  chmod +x /usr/local/bin/duckdns.sh
  ( crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/duckdns.sh" ) | crontab -
  /usr/local/bin/duckdns.sh || true
  echo "  DuckDNS cron installed (updates every 5 min)."
else
  echo "  Skipped DuckDNS (no token/subdomain given). Configure duckdns/duckdns.sh manually."
fi

echo ""
echo "======================================================================"
echo " FleetPanel is up:  https://$DOMAIN"
echo ""
echo " Your agent ENROLLMENT SECRET (use it in setup-agent.bat):"
echo "     $ENROLL"
echo ""
echo " Admin login: username 'admin'. Get the one-time password with:"
echo "     journalctl -u fleetpanel | grep -A2 'INITIAL ADMIN'"
echo " Then log in and change it immediately."
echo "======================================================================"
