#!/bin/sh
set -eu
cd /opt/fleetpanel
export FLEETPANEL_OS=1
export LOCALAPPDATA="${XDG_STATE_HOME:-$HOME/.local/state}/fleetpanel"
mkdir -p "$LOCALAPPDATA"
exec /opt/fleetpanel/.venv/bin/python /opt/fleetpanel/fleetos/launch.py
