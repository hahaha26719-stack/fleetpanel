# Kid Launcher & Simplified Apps

After a child signs in with their FleetPanel account, instead of the normal
Windows desktop they get a **full-screen, child-friendly launcher** with big
tiles for the allowed apps. Everything is enforced *inside our apps* (no
`/etc/hosts` or registry needed for the kid use-case).

## The apps

| App | File | What it does |
|-----|------|--------------|
| **Launcher** | `launcher.py` | 3 big tiles (Notepad / Slides / Web). Only shows apps allowed by the `app_mode` policy. "Sign out" ends the session. |
| **Notepad** | `kidnotepad.py` | Tabs: **Write**, **My Files** (save/open locally + roams to the Pi), **Pictures** (search via the Pi, filtered by `picture_mode`), **Together** (collaborate by room code). |
| **Slides** | `kidppt.py` | Simple slide maker (title + text per slide), save/open, **Together** collaboration. |
| **Web** | `kidbrowser.py` | Our own browser (renders real sites via Windows WebView2). Every page is checked against `web_mode` before loading; blocked pages show a friendly notice. |

## The 3 admin "mode" policies

In the panel, under **Kid Launcher**, each has a dropdown + an exceptions list:

- **web_mode** — *Allow everything except…* (blocklist) or *Block everything except…* (allowlist) of website domains.
- **app_mode** — which of notepad / powerpoint / edge the launcher shows.
- **picture_mode** — which picture searches are allowed (keywords/sources).

Set them per-group or per-user just like any other policy (user overrides group).

## Why picture search works even when the web is blocked

The browser blocks the open web **inside the app**. Picture search is a
*different* app that calls **your Pi**, which fetches images from Openverse
(free, no key, openly-licensed) and applies the `picture_mode` policy. The PC
only ever talks to the Pi, so blocking the open web doesn't break pictures.

## Collaboration (room codes)

In Notepad or Slides, open **Together**, type a room code, and share it. The Pi
keeps the shared document and syncs every ~3 seconds (last-write-wins by
version). Light enough for classroom use on the Pi.

## Session lifecycle

```
Boot → startup_cleanup(): restore hosts from backup + wipe local user data
     → FleetPanel login screen
     → kid signs in → policies applied, roaming files pulled, kid_session.json written
     → launcher opens full-screen; kid uses the allowed apps
     → "Sign out" → push files to Pi + revert policies → REBOOT
     → (next boot starts clean again)
```

- **Files are safe:** local copies are wiped on reboot, but the master copy lives
  on the Pi and re-downloads at next login, so a kid's notes/slides follow them.
- **Hosts is protected:** a pristine backup is taken once; every boot restores it.

## Setup

`setup-agent.bat` now copies all the kid app files and installs `pywebview`
(the browser engine; WebView2 ships with Windows 10/11). Re-run it on each PC to
get the new apps, or copy the `kid*.py` + `launcher.py` + `login_app.py` files
into `C:\FleetAgent` and `pip install pywebview`.

## The kid cannot escape (kiosk lock)

- The **login app** and **launcher** block the window-close (X), **Alt+F4**, and
  Ctrl+W/Ctrl+Q — the kid can't close them to reach the desktop.
- Child apps are launched with **`pythonw.exe`** so there is **no console
  window** to close and kill them.
- If the launcher process is somehow killed, the login app **relaunches it
  automatically** (every ~1.5s) while the session is active.
- The **only** ways out are: the big **Sign out** button (which reboots), or the
  **admin-only Ctrl+Alt+Q** (requires a FleetPanel admin password).
- Always launch the login app with `pythonw.exe` (not `python.exe`) in
  production so there's no console window at all. The Startup entry in
  `LOGIN-APP.md` already uses `pythonw`.

> In `--windowed` TEST mode these locks are DISABLED so you can close things
> while testing and not trap yourself.

## Testing safely

Run any app windowed, no kiosk, no reboot:
```bat
python C:\FleetAgent\login_app.py --windowed
python C:\FleetAgent\launcher.py --windowed
python C:\FleetAgent\kidnotepad.py --windowed
```
In `--windowed` mode, sign-out does NOT reboot (it just returns to the login
screen) so you can test freely.
