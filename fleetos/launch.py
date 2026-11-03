#!/usr/bin/env python3
"""Start the unchanged FleetPanel launcher inside the FleetOS session."""
from __future__ import annotations
import os, runpy, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"
if not (AGENT_DIR / "launcher.py").is_file():
    raise SystemExit(f"FleetPanel agent directory not found: {AGENT_DIR}")
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
runpy.run_path(str(AGENT_DIR / "launcher.py"), run_name="__main__")
