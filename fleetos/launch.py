#!/usr/bin/env python3
"""Start the unchanged FleetPanel launcher inside the FleetOS session."""
from __future__ import annotations
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"
LAUNCHER = AGENT_DIR / "launcher.py"
if not LAUNCHER.is_file():
    raise SystemExit(f"FleetPanel launcher not found: {LAUNCHER}")

state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
fleet_state = state_root / "fleetpanel"
fleet_state.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("LOCALAPPDATA", str(fleet_state))
os.environ.setdefault("FLEETPANEL_OS", "1")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(AGENT_DIR))
os.chdir(AGENT_DIR)

import agent
from fleetos import linux_agent_bridge
linux_agent_bridge.install(agent)

# Load the original launcher without changing its source. On Linux, suppress
# the NWEA Windows .exe tile until an NWEA-approved Linux testing client exists.
spec = importlib.util.spec_from_file_location("fleetpanel_original_launcher", LAUNCHER)
if spec is None or spec.loader is None:
    raise SystemExit("Could not load original FleetPanel launcher")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
launcher.APPS = [item for item in launcher.APPS
                 if not (item[0] == "nys_testing" or
                         (isinstance(item[4], str) and item[4].lower().endswith(".exe")))]
launcher.build().mainloop()
