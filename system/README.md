# System

This directory is reserved for the base operating-system integration that makes FleetPanel the device shell.

Planned responsibilities:

- systemd service and target definitions;
- graphical session startup and automatic FleetPanel login-shell launch;
- user/session isolation and writable state directories;
- network startup and recovery;
- update and rollback services;
- power, suspend and reboot integration;
- kiosk restrictions enforced by Linux rather than Windows registry calls.

The base system should be minimal for 4 GB RAM / 32 GB eMMC. The FleetPanel student interface remains the primary interactive environment; a general desktop is not the default student session.

Do not copy Windows-only PowerShell, registry or batch lockdown scripts here and assume they work on Linux. Each policy needs a Linux-native implementation and tests.
