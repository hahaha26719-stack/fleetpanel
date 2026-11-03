#!/usr/bin/env bash
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then echo "Run as root: sudo $0" >&2; exit 1; fi
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/out"
WORK="$OUT/live-build"
mkdir -p "$OUT"
for cmd in lb debootstrap mksquashfs xorriso; do
  command -v "$cmd" >/dev/null || { echo "Missing build tool: $cmd" >&2; exit 1; }
done
rm -rf "$WORK"
mkdir -p "$WORK"
cd "$WORK"
lb config \
  --distribution trixie \
  --architectures amd64 \
  --binary-images iso-hybrid \
  --bootloaders grub-efi,syslinux \
  --debian-installer false \
  --archive-areas "main contrib non-free-firmware" \
  --apt-recommends false \
  --iso-application "FleetPanel OS" \
  --iso-volume "FLEETPANEL_OS"
mkdir -p config/package-lists
cp "$ROOT/build/debian/packages.list" config/package-lists/fleetpanel.list.chroot
# Include tools needed for diagnostics and image setup.
printf '\nrsync\nlive-boot\nlibinput-tools\npciutils\nusbutils\niw\nrfkill\n' >> config/package-lists/fleetpanel.list.chroot
mkdir -p config/includes.chroot/opt/fleetpanel
rsync -a --delete --exclude='.git' "$ROOT/" config/includes.chroot/opt/fleetpanel/
chmod 0755 config/includes.chroot/opt/fleetpanel/fleetos/session.sh
mkdir -p config/hooks/normal
cat > config/hooks/normal/010-fleetpanel.hook.chroot <<'HOOK'
#!/bin/sh
set -eu
python3 -m venv --system-site-packages /opt/fleetpanel/.venv
/opt/fleetpanel/.venv/bin/pip install --no-cache-dir -r /opt/fleetpanel/fleetos/requirements-linux.txt
HOOK
chmod 0755 config/hooks/normal/010-fleetpanel.hook.chroot
mkdir -p config/includes.chroot/usr/share/xsessions
cp "$ROOT/build/debian/fleetpanel.desktop" config/includes.chroot/usr/share/xsessions/fleetpanel.desktop
lb build
mkdir -p "$OUT"
cp ./*.iso "$OUT/fleetpanel-os-bobba-amd64.iso"
echo "Created $OUT/fleetpanel-os-bobba-amd64.iso"
