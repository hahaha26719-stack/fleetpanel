# BOBBA hardware profile

Target: Acer Chromebook 311 CB311-9H / CB311-9HT family, board name BOBBA, Intel Gemini Lake.

## Required hardware

| Function | Linux driver stack to validate |
|---|---|
| Intel UHD Graphics 600 | `i915` + Mesa |
| Internal display | DRM/KMS + panel/EDID discovery |
| Keyboard | Linux HID/input stack |
| Touchpad | I2C-HID or device-specific kernel driver + libinput |
| Wi-Fi (Intel Wireless-AC 9560 on applicable SKUs) | `iwlwifi`, `iwlmvm`, matching `linux-firmware` |
| Bluetooth (applicable SKUs) | `btusb`, `btintel`, firmware |
| Audio | Gemini Lake Chromebook-specific ALSA/UCM/SOF/AVS configuration; exact codec must be identified |
| eMMC | MMC/SDHCI kernel stack |

## Optional hardware

- Webcam: `uvcvideo` if the camera enumerates as a standard UVC device.
- microSD reader: controller is not yet identified; validate only if present.

## Explicitly not required

- Touchscreen support. The target devices in this project do not have touchscreens.

## Touchpad release gate

The touchpad is mandatory. A device cannot pass acceptance unless pointer movement, physical click, tap-to-click, two-finger scrolling and reliable wake-from-suspend behavior work.

## Unknowns that must not be guessed

CB311-9H and CB311-9HT are sold in multiple configurations. Exact Wi-Fi, touchpad, audio codec, camera and card-reader IDs must be discovered from a real device or reliable board-level hardware data before claiming exact support. Do not infer the base BOBBA audio codec from BOBBA360 reports.

## Validation commands for the first physical test

```sh
lspci -nnk
lsusb
cat /proc/bus/input/devices
libinput list-devices
rfkill list
iw dev
aplay -l
arecord -l
lsblk -o NAME,MODEL,SIZE,TRAN
dmesg | grep -Ei 'i2c|hid|touchpad|iwlwifi|firmware|snd|audio|mmc'
```

Collect these outputs from one representative unit before finalizing the hardware manifest.
