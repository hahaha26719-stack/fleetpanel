# Boot

FleetPanel OS targets x86_64 UEFI boot on the BOBBA Chromebook firmware configuration.

Planned boot flow:

1. UEFI firmware starts the signed/approved bootloader.
2. Bootloader loads the Linux kernel and initramfs.
3. Linux initializes eMMC, graphics, keyboard, touchpad, Wi-Fi and audio.
4. systemd starts the graphical login/session stack.
5. The dedicated FleetPanel session starts `fleetos/launch.py`.
6. `fleetos/launch.py` starts the existing `agent/launcher.py` as the primary shell.

The bootloader and kernel must remain replaceable by the image build. Do not write firmware, change Chromebook security settings, or flash devices as part of an ordinary OS installation.

## Current state

This directory documents the target boot design. The repository does not yet contain a complete EFI image, initramfs, installer, or tested BOBBA bootloader configuration.
