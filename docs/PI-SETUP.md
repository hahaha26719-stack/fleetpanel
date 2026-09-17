# Running FleetPanel on a Banana Pi (Armbian) — dual-use guide

This runs FleetPanel **alongside** your existing slideshow web app (port 5000)
on the same Banana Pi P2 Zero, without disturbing it.

- Slideshow keeps running on **:5000** (untouched).
- FleetPanel runs internally on **:8090**.
- Tuned for ~512 MB RAM: 1 gunicorn worker + threads, 200 MB memory cap,
  low CPU priority, and a swap file so the board stays stable.

---

## Step 1 — get the code onto the Pi

SSH into the Pi, then:

```bash
git clone https://github.com/hahaha26719-stack/fleetpanel.git
cd fleetpanel
```

## Step 2 — choose how the internet reaches it

Your Pi is behind a home router, so you need a way in from outside. Two options:

### Option A — Cloudflare Tunnel (recommended: free, no port-forwarding, free HTTPS)
Nothing is exposed on your home IP; Cloudflare proxies it. Requires a domain
added to a (free) Cloudflare account.

```bash
sudo ./setup-pi.sh --cloudflared
```

Then finish the tunnel (one-time, interactive):

```bash
cloudflared tunnel login                     # opens a link; authorise your domain
cloudflared tunnel create fleetpanel
cloudflared tunnel route dns fleetpanel panel.yourdomain.com
```

Create `/etc/cloudflared/config.yml`:
```yaml
tunnel: fleetpanel
credentials-file: /root/.cloudflared/<TUNNEL-ID>.json
ingress:
  - hostname: panel.yourdomain.com
    service: http://127.0.0.1:8090
  - service: http_status:404
```

Install it as a service so it starts on boot:
```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

Your panel is now at `https://panel.yourdomain.com` (HTTPS handled by Cloudflare).

### Option B — DuckDNS + router port-forwarding (uses fleetpanel.duckdns.org)
Use this if you don't have a Cloudflare domain and want to use the DuckDNS name
you already made.

```bash
sudo ./setup-pi.sh --duckdns fleetpanel.duckdns.org <YOUR_TOKEN> fleetpanel
```

Then, **on your home router**, forward external ports **80** and **443** to the
Pi's local IP. Finally get HTTPS:
```bash
sudo certbot --nginx -d fleetpanel.duckdns.org
```

> ⚠️ Port-forwarding exposes the Pi directly on your home connection. The
> Cloudflare Tunnel (Option A) is safer because it doesn't. Also: the DuckDNS
> token you shared in chat should be **recreated** on duckdns.org since it was
> exposed.

## Step 3 — get your credentials

The script prints your **enrollment secret**. Get the admin password:
```bash
journalctl -u fleetpanel | grep -A2 'INITIAL ADMIN'
```
Log in, change the admin password immediately.

## Step 4 — connect the Windows PCs

On each PC (as Administrator):
```bat
setup-agent.bat https://panel.yourdomain.com  <enrollment_secret>
```
(or your DuckDNS URL if you used Option B).

---

## Living with a small board + 150 PCs — be realistic

The P2 Zero is modest. FleetPanel is light (agents just poll occasionally), but:

- **Stagger agent check-ins.** Don't have 150 PCs hit it at the same second.
  The agent applies policy at logon; if you add periodic re-checks, spread them
  over several minutes (a random delay).
- **Roaming file sync is the heavy part.** If users store big files, the Pi's
  SD card + RAM will struggle. Keep roaming data small, or point
  `FLEET_DATA` at attached USB storage and cap per-user size.
- **Watch memory:** `free -h` and `systemctl status fleetpanel`. The service is
  capped at 200 MB so it can't starve your slideshow.
- **Back up** `fleet.db` + `userdata/` regularly (SD cards fail).

If it ever feels overloaded, moving just FleetPanel to a small VPS later is a
copy of `fleet.db` + `userdata/` away — nothing else changes.

## Useful commands

```bash
systemctl status fleetpanel          # is it running?
journalctl -u fleetpanel -f          # live logs
sudo systemctl restart fleetpanel    # restart after changes
free -h                              # memory
```
