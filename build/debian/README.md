# Debian image build

The initial image target is a minimal Debian-based x86_64 UEFI system for BOBBA. Debian is the selected starting point for this branch, subject to kernel/audio validation.

The image must include:

- UEFI boot support and a maintained kernel;
- Xorg or another tested display server plus a minimal session manager;
- Python 3, Tkinter and Pillow for the existing FleetPanel apps;
- WebKitGTK and a Linux pywebview backend for the existing browser;
- NetworkManager and Intel wireless firmware;
- Intel graphics userspace and Chromebook-specific audio configuration;
- FleetOS integration and the unchanged `agent/` tree.

Do not pin an old kernel just because the base distribution supplies it. The BOBBA touchpad, wireless, display and Chromebook audio must be tested against the selected kernel before an image is considered ready.

## Build state

This folder is a build specification only. A reproducible live-build configuration, installer, EFI image and CI build are not yet implemented. The first build should be a disposable test image, not an installer intended for the 100 school devices.
