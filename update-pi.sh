#!/usr/bin/env bash
# ===================================================================
#  FleetPanel — one-command UPDATE for the Pi (server side).
#  Pulls latest code and restarts the service, KEEPING your users/DB.
#  Run from the cloned repo dir:  sudo ./update-pi.sh
# ===================================================================
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo."; exit 1; fi

cd "$(dirname "$0")"
echo "Pulling latest code..."
git pull --ff-only || { echo "git pull failed (local changes?)"; exit 1; }

# setup-pi-lan.sh is idempotent: it updates code but preserves .env/fleet.db/userdata
./setup-pi-lan.sh
echo "Pi updated (users and settings preserved)."
