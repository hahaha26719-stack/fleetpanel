#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET=/opt/fleetpanel
if [[ "$(id -u)" -ne 0 ]]; then echo "Run with sudo: $0" >&2; exit 1; fi
if [[ ! -f /etc/debian_version ]]; then echo "Debian is required." >&2; exit 1; fi
if [[ "$(dpkg --print-architecture)" != "amd64" ]]; then echo "amd64 is required." >&2; exit 1; fi
apt-get update
mapfile -t packages < <(grep -Ev '^[[:space:]]*(#|$)' "$ROOT/build/debian/packages.list")
DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"
if ! id fleetpanel >/dev/null 2>&1; then useradd --create-home --shell /bin/bash fleetpanel; fi
install -d -o fleetpanel -g fleetpanel /var/lib/fleetpanel "$TARGET"
rsync -a --delete --exclude='.git' "$ROOT/" "$TARGET/"
chown -R root:root "$TARGET"
chmod -R a+rX "$TARGET"
python3 -m venv --system-site-packages "$TARGET/.venv"
"$TARGET/.venv/bin/pip" install --upgrade pip
"$TARGET/.venv/bin/pip" install -r "$TARGET/fleetos/requirements-linux.txt"
install -m 0644 "$TARGET/build/debian/fleetpanel.desktop" /usr/share/xsessions/fleetpanel.desktop
install -m 0755 "$TARGET/fleetos/session.sh" "$TARGET/fleetos/session.sh"
cat <<'NOTICE'
FleetPanel OS test components installed.
This is NOT a bootable image or a disk installer. Log in to the test desktop and
select the FleetPanel session after setting a password for the fleetpanel account.
It does not configure automatic
graphical login, partition storage, flash firmware or enforce kiosk restrictions.
The Linux policy bridge intentionally rejects unsupported Windows policies.
NOTICE
