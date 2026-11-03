# Debian image build

The first target is a minimal Debian 13 (trixie) amd64 live image for BOBBA. It is a development image, not a school deployment image.

## Build host

Use a Debian 13 amd64 build host or a matching container with `live-build`, `debootstrap`, `squashfs-tools`, `xorriso` and `git`. Run:

```sh
sudo apt-get install live-build debootstrap squashfs-tools xorriso git
./build/debian/build-live-image.sh
```

The script creates a disposable live-build workspace under `out/` and produces an ISO there. The first ISO is a diagnostic/live test image; it does not install to internal eMMC.

## Included system

- Debian kernel and UEFI GRUB boot path;
- Xorg/Openbox diagnostic session;
- Python/Tkinter/Pillow and WebKitGTK dependencies;
- NetworkManager and Intel wireless firmware package;
- Bluetooth and PipeWire/ALSA tools;
- FleetPanel source tree and Linux integration.

## Important limitations

- The current agent contains Windows-only policy hooks. The Linux bridge rejects them instead of pretending they work.
- A kiosk login service is included as an integration unit, but automatic graphical login and security hardening are not enabled by the image builder yet.
- The browser must be tested against the actual installed pywebview/WebKitGTK versions.
- The NYS tile still names a Windows NWEA executable. It is not a working Linux testing client.
- Touchpad, Wi-Fi, graphics and audio need hands-on validation on a BOBBA Chromebook.
- Do not install this image on school devices until NWEA secure testing has an approved solution.
