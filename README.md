# FleetPanel — Centralized Windows User, Group & Policy Management

Manage users, groups, and policies for a fleet of Windows PCs from a single
web panel, with per-user roaming data. Designed to run on an always-on Linux VM
and be reached via a **DuckDNS** domain — plus a full **Windows lockdown** layer
so policies actually stick against standard (non-admin) users.

---

## ⚠️ Read this first — the honest security model

This project has two parts:

1. **FleetPanel** (server + agent) — convenient central management of users,
   groups, and policies (web restrictions, printing, File Explorer, removable
   media, etc.). Policies roam with the user across any managed PC.
2. **Lockdown** (`lockdown/`) — Windows-level enforcement so a **standard
   (non-admin) user cannot bypass** the policies.

**What is genuinely un-bypassable, and what is not:**

- ✅ For a **standard user**, the combined lockdown (standard account + UAC
  hardening + WDAC kernel default-deny + strict ACLs + BitLocker/Secure Boot)
  leaves no software or offline escape route.
- ❌ An **administrator with physical access can always reverse it.** This is a
  deliberate property of Windows (and of Active Directory and every MDM) — it's
  what separates device management from malware. No account, agent, or
  "hardware block" changes this. If someone can become admin/SYSTEM, they win;
  the defense is preventing that (standard users), not stacking blocks on top.
- For a real 150-seat fleet, enforce all of this via **Active Directory Group
  Policy** or **Intune** so it applies at boot, below the user.

---

## Repository layout

| Path | Purpose |
|------|---------|
| `server/` | Flask web panel + REST API + SQLite (runs on the VM) |
| `agent/` | Windows agent: applies policies, syncs roaming data |
| `lockdown/` | PowerShell scripts for Windows-level enforcement |
| `duckdns/` | DuckDNS dynamic-DNS updaters |
| `docs/` | Detailed deployment guide |
| `setup-server.sh` | One-shot server installer for a full VM |
| `setup-pi.sh` | Optimised installer for a Banana Pi / low-RAM ARM board (dual-use) |
| `setup-agent.bat` | One-shot agent installer for each Windows PC |

---

## Where to host the server (always-on options)

The panel must run 24/7 so agents can check in. Good choices:

- **Google Cloud `e2-micro`** — free forever (1 vCPU / 1 GB, US region). Great fit.
- **Cheap VPS** (Hetzner / DigitalOcean / Vultr, ~$4–6/mo) — most reliable for a
  real fleet.
- **Oracle Cloud Ampere** — most generous free tier if you use it.

The setup script works on any Ubuntu/Debian VM.

**Running on a Banana Pi / Raspberry Pi (Armbian/Debian)?** Use the optimised,
dual-use installer instead — it runs alongside an existing service (e.g. a
slideshow on port 5000) without disturbing it. See **`docs/PI-SETUP.md`** and
`setup-pi.sh`.

---

## 1. Set up the server (on your VM)

```bash
git clone https://github.com/hahaha26719-stack/fleetpanel.git
cd fleetpanel
sudo ./setup-server.sh yourname.duckdns.org  <duckdns_token>  <duckdns_subdomain>
```

This installs Python + nginx + certbot, runs FleetPanel under gunicorn/systemd,
sets up HTTPS via Let's Encrypt, and installs the DuckDNS cron updater.

At the end it prints your **enrollment secret**. Get the initial admin password:

```bash
journalctl -u fleetpanel | grep -A2 'INITIAL ADMIN'
```

Log in at `https://yourname.duckdns.org` and **change the admin password**.

## 2. Install the agent (on each Windows PC, as Administrator)

```bat
setup-agent.bat https://yourname.duckdns.org  <enrollment_secret>
```

Requires Python on the PC, or freeze the agent to `FleetAgent.exe` first
(see `agent/BUILD.md`). The agent enrolls the PC and applies each user's
effective policies at logon; roaming data syncs down at logon and up at logoff.

## 3. Lock down the PCs (make policies un-bypassable for standard users)

Run these on each PC as Administrator (or push via Group Policy / Intune for a
fleet). See `lockdown/README.md` for the full model and order.

```powershell
lockdown\New-StandardUser.ps1 -Username alice -FullName "Alice Smith"
lockdown\Harden-Machine.ps1
lockdown\New-WDACDefaultDeny.ps1 -OutDir C:\WDAC -Audit    # audit first!
lockdown\New-WDACDefaultDeny.ps1 -OutDir C:\WDAC           # then enforce
lockdown\Set-StrictPermissions.ps1 -AgentPath C:\FleetAgent
lockdown\Enable-Firmware-Encryption.ps1                    # BitLocker/Secure Boot
```

---

## Using the panel

- **Users** — create accounts, reset passwords, enable/disable, delete.
- **Groups** — create groups, add/remove members. **Group policies apply to
  every member** — manage many users at once.
- **Policies** — per-group or per-user. **User policies override group policies.**
  Categories include Web Restrictions, Printing, File Explorer, Removable Media,
  Start & Taskbar, Security, Network, Applications, Desktop, Updates, Session.
- **Roaming** — a user's data and effective policies follow them to any managed
  PC.

Add a new policy by adding one entry to `server/policies.py`; the panel and
agent pick it up automatically.

---

## Local development / testing

```bash
cd server
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python app.py           # http://localhost:8080  (dev only)
```

See `docs/DEPLOY.md` for the detailed production/hardening guide.
