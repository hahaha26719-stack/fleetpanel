#!/usr/bin/env python3
"""Read-only hardware and runtime preflight for FleetPanel OS."""
from __future__ import annotations
import json, os, shutil, subprocess
from pathlib import Path

def command_output(argv):
    exe = shutil.which(argv[0])
    if not exe: return None
    try:
        return subprocess.run([exe, *argv[1:]], text=True, capture_output=True, timeout=8).stdout.strip()
    except Exception:
        return None

def main():
    report = {
        "architecture": os.uname().machine,
        "required": {
            "touchpad": command_output(["libinput", "list-devices"]),
            "wifi": command_output(["iw", "dev"]),
            "graphics": command_output(["lspci", "-nnk"]),
            "audio": command_output(["aplay", "-l"]),
            "network_manager": shutil.which("nmcli"),
        },
        "optional": {
            "webcam": Path("/dev/video0").exists(),
            "microsd_or_removable_media": command_output(["lsblk", "-o", "NAME,MODEL,SIZE,TRAN"]),
        },
    }
    report["checks"] = {
        "amd64": report["architecture"] in ("x86_64", "amd64"),
        "touchpad_tool_present": report["required"]["touchpad"] is not None,
        "wifi_tool_present": report["required"]["wifi"] is not None,
        "audio_tool_present": report["required"]["audio"] is not None,
    }
    print(json.dumps(report, indent=2))
    # This only checks that diagnostic tools exist; hardware itself must be
    # reviewed from the printed report and validated on a real BOBBA unit.
    return 0 if report["checks"]["amd64"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
