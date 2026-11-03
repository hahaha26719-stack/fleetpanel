# FleetOS integration

This directory contains Linux-specific code. It must not modify the original files in `agent/`.

## Primary shell

The target user session starts the existing FleetPanel launcher. Linux-specific state paths, process startup, system actions, policy enforcement and browser-engine selection belong here.

## Preservation

The launcher and student apps are currently Windows-oriented in several places. In particular:

- `agent.py` treats Windows registry/command/app-block operations as dry-run behavior on non-Windows systems.
- `kidcommon.py` derives writable state from Windows environment variables; the Linux launcher must provide a safe writable `LOCALAPPDATA` equivalent before importing the app modules.
- `kidbrowser.py` uses pywebview and needs a verified WebKitGTK backend on Linux.
- the NYS Testing tile currently points to a Windows executable path.

Never report these functions as working on Linux until the relevant Linux bridge is implemented and tested. Unsupported security policies must fail closed and be clearly reported to administrators.
