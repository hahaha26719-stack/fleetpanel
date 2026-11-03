# FleetPanel OS

FleetPanel OS turns the existing FleetPanel student environment in `agent/` into the primary user-facing operating system shell for supported Acer Chromebook 311 BOBBA devices.

## Non-negotiable preservation rule

The existing `agent/` directory is the product's application and shell source of truth. Its existing files are retained byte-for-byte while Linux integration is developed outside that directory. The OS boots into the FleetPanel login/launcher rather than presenting a general-purpose desktop.

## Repository layout

- `boot/` — UEFI boot and session handoff documentation/configuration.
- `system/` — base operating-system service design.
- `drivers/bobba/` — Acer Chromebook 311 BOBBA hardware profile and driver requirements.
- `fleetos/` — Linux-specific integration and compatibility code.
- `build/debian/` — reproducible Debian-based image build inputs.
- `agent/` — existing FleetPanel login, launcher and student applications, preserved.

## Target hardware

- Board family: BOBBA (Acer Chromebook 311 CB311-9H / CB311-9HT).
- CPU/GPU: Intel Gemini Lake, Celeron N4000/N4020 variants, Intel UHD Graphics 600.
- RAM/storage target: 4 GB RAM and 32 GB eMMC.
- Required: internal display, keyboard, touchpad, Wi-Fi, Bluetooth and working audio.
- Not required: touchscreen.
- Optional: webcam and microSD reader.

## Important compatibility boundary

The existing agent was written for Windows. It contains Windows registry, shell, reboot, policy and WebView2 assumptions. Linux integration must be explicit and live outside `agent/`; a dry-run path in the original code is not equivalent to enforcing a Linux policy. The Linux bridge must fail closed for unsupported security policies rather than claim they are enforced.

The existing browser uses pywebview/WebView2-oriented behavior and needs a tested Linux WebKitGTK backend. The NYS Testing tile currently points to a Windows NWEA executable; that path is not a working Linux implementation. NWEA secure testing remains a release blocker until NWEA explicitly supports/approves the environment.

## Build status

This branch is an initial OS foundation, not a bootable or tested release yet. Do not install it on school devices until the image boots on BOBBA, the required drivers pass hardware tests, FleetPanel login/apps work, and NYS/NWEA testing has an approved supported path.
