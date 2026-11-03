#!/usr/bin/env python3
"""Linux entry point for the existing FleetPanel shell.

This file deliberately starts the existing agent/launcher.py without editing
that source tree. Linux-specific compatibility is installed by
fleetos.linux_agent_bridge before the launcher imports its agent module.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"

if not (AGENT_DIR / "launcher.py").is_file():
    raise SystemExit(f"FleetPanel agent directory not found: {AGENT_DIR}")

# Make both the OS integration package and the original top-level agent
# modules importable regardless of the current working directory.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(AGENT_DIR))

# Give the unchanged Windows-era apps a Linux writable state location.
state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
fleet_state = state_root / "fleetpanel"
fleet_state.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("LOCALAPPDATA", str(fleet_state))
os.environ.setdefault("FLEETPANEL_OS", "1")

os.chdir(AGENT_DIR)

import agent  # noqa: E402
from fleetos import linux_agent_bridge  # noqa: E402

linux_agent_bridge.install(agent)

# Run the original launcher in this process. Its source remains unchanged.
runpy.run_path(str(AGENT_DIR / "launcher.py"), run_name="__main__")
