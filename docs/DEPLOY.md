# Deploying FleetPanel on Oracle Cloud + DuckDNS

This guide sets up the panel for **~150 users** on an Oracle Cloud VM, reachable
at `https://YOURNAME.duckdns.org`, served over HTTPS.

> ⚠️ You are running an authentication + policy system that manages real PCs.
> Do **every** step in the "Security hardening" section before you trust it with
> real accounts. For a production org, Windows Server + Active Directory remains
> the safer, purpose-built option.

---

## 1. Create the Oracle Cloud VM

1. In Oracle Cloud, create a **Compute instance**. The free-tier
   **Ampere A1 (ARM)** shape (up to 4 OCPU / 24 GB RAM) easily handles 150 users.
2. OS: **Ubuntu 22.04** (or Oracle Linux). Save your SSH key.
3. Assign a **public IPv4** address.

## 2. Open the firewall (two layers)

Oracle blocks ports at both the cloud and OS level.

**a) VCN Security List / NSG** — add ingress rules for:
- TCP **80** (HTTP, for Let's Encrypt) from `0.0.0.0/0`
- TCP **443** (HTTPS) from `0.0.0.0/0`

**b) On the VM** (Ubuntu uses iptables by default on Oracle images):
```bash
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 3. Install the app

```bash
sudo apt update && sudo apt install -y python3-venv nginx certbot python3-certbot-nginx git
sudo mkdir -p /opt/fleetpanel && sudo chown $USER /opt/fleetpanel
# copy the server/ folder here (git clone or scp), then:
cd /opt/fleetpanel/server
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

Generate stable secrets (so sessions/tokens survive restarts):
```bash
export FLEET_SECRET="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
export FLEET_ENROLL_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')"
```
Save both in `/opt/fleetpanel/server/.env` and note the enroll secret for agents.

## 4. Run it with gunicorn under systemd

Create `/etc/systemd/system/fleetpanel.service`:
```ini
[Unit]
Description=FleetPanel
After=network.target

[Service]
WorkingDirectory=/opt/fleetpanel/server
EnvironmentFile=/opt/fleetpanel/server/.env
ExecStart=/opt/fleetpanel/server/.venv/bin/gunicorn -w 3 -b 127.0.0.1:8080 app:app
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now fleetpanel
# grab the one-time admin password from the first run:
sudo journalctl -u fleetpanel | grep -A2 "INITIAL ADMIN"
```

## 5. Point DuckDNS at the VM

1. Get a token at https://www.duckdns.org and create the subdomain `YOURNAME`.
2. On the VM, set env vars and install the cron job:
```bash
sudo cp duckdns/duckdns.sh /usr/local/bin/duckdns.sh && sudo chmod +x /usr/local/bin/duckdns.sh
echo '*/5 * * * * DUCKDNS_DOMAIN=YOURNAME DUCKDNS_TOKEN=xxxx /usr/local/bin/duckdns.sh' | sudo crontab -
/usr/local/bin/duckdns.sh   # run once now; should print OK
```

## 6. HTTPS with nginx + Let's Encrypt

Create `/etc/nginx/sites-available/fleetpanel`:
```nginx
server {
    listen 80;
    server_name YOURNAME.duckdns.org;
    client_max_body_size 200M;   # allow roaming file uploads
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/fleetpanel /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d YOURNAME.duckdns.org   # issues + auto-renews the cert
```

Visit `https://YOURNAME.duckdns.org` and log in as `admin`.

## 7. Deploy the agent to PCs

See `agent/BUILD.md`. Point `agent_config.json` at
`https://YOURNAME.duckdns.org` and set `enroll_secret` to the value from step 3.

---

## Security hardening (do these before real use)

- [ ] Change the seeded `admin` password immediately.
- [ ] Keep `FLEET_ENROLL_SECRET` set so random machines can't enroll.
- [ ] HTTPS only — never expose port 8080 directly; only nginx faces the internet.
- [ ] Put the VM's `.env`, `fleet.db`, and `userdata/` on a backed-up volume.
- [ ] Add rate-limiting / fail2ban on `/login` and `/api/login` to slow brute force.
- [ ] Consider disk quotas per user for `userdata/` (roaming storage).
- [ ] Rotate device tokens if a PC is lost; delete its device row in the DB.
- [ ] Review the agent limitations in `agent/BUILD.md` — local admins on a PC can
      undo registry policies; this is not a substitute for domain enforcement.

## Backups

`fleet.db` (SQLite) + the `userdata/` directory are the entire state. Back them up:
```bash
sudo systemctl stop fleetpanel
tar czf fleet-backup-$(date +%F).tgz /opt/fleetpanel/server/fleet.db /opt/fleetpanel/server/userdata
sudo systemctl start fleetpanel
```
