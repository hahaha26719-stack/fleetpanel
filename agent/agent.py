"""
FleetPanel Windows Agent
========================

Runs on each managed Windows PC. On user login it:
  1. Enrolls the PC (once) and stores a device token.
  2. Authenticates the user against FleetPanel.
  3. Downloads the user's *effective* policies and applies them (registry edits,
     commands, app-blocking) — so a user gets the same policies on ANY PC.
  4. Two-way syncs the user's roaming data folder with the server.

Requires Python 3 on the target PC (or freeze to .exe with PyInstaller — see
agent/BUILD.md). Registry/app-block operations require Administrator rights;
run the agent as SYSTEM/Admin via a scheduled task at logon.

Config is read from agent_config.json next to this file, or env vars:
  FLEET_SERVER   e.g. https://yourname.duckdns.org
  FLEET_ENROLL_SECRET  (optional, must match server FLEET_ENROLL_SECRET)
"""

import os
import sys
import json
import socket
import getpass
import subprocess
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "agent_config.json")
TOKEN_PATH = os.path.join(HERE, "device_token.json")
IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import winreg  # noqa

HIVES = {}
if IS_WINDOWS:
    HIVES = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
REGTYPES = {}
if IS_WINDOWS:
    REGTYPES = {"REG_DWORD": winreg.REG_DWORD, "REG_SZ": winreg.REG_SZ}


# --------------------------------------------------------------------- config/io
def load_config():
    cfg = {"server": os.environ.get("FLEET_SERVER", "").rstrip("/"),
           "enroll_secret": os.environ.get("FLEET_ENROLL_SECRET", "")}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    cfg["server"] = cfg.get("server", "").rstrip("/")
    if not cfg["server"]:
        sys.exit("No server configured. Set FLEET_SERVER or create agent_config.json.")
    return cfg


def _request(cfg, method, path, token=None, json_body=None, raw=None, headers=None):
    url = cfg["server"] + path
    data = None
    hdrs = dict(headers or {})
    if json_body is not None:
        data = json.dumps(json_body).encode()
        hdrs["Content-Type"] = "application/json"
    elif raw is not None:
        data = raw
    if token:
        hdrs["X-Agent-Token"] = token
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def enroll(cfg):
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            return json.load(f)["token"]
    hostname = socket.gethostname()
    status, body = _request(cfg, "POST", "/api/enroll",
                            json_body={"hostname": hostname,
                                       "enroll_secret": cfg.get("enroll_secret", "")})
    if status != 200:
        sys.exit(f"Enrollment failed ({status}): {body!r}")
    tok = json.loads(body)["token"]
    with open(TOKEN_PATH, "w") as f:
        json.dump({"token": tok}, f)
    print(f"[agent] enrolled {hostname}")
    return tok


# --------------------------------------------------------------- policy applying
def apply_registry(spec, value):
    if not IS_WINDOWS:
        print(f"[dry-run] registry {spec['hive']}\\{spec['path']}\\{spec['name']} <- {value}")
        return
    root = HIVES[spec["hive"]]
    key = winreg.CreateKeyEx(root, spec["path"], 0, winreg.KEY_SET_VALUE)
    regtype = REGTYPES[spec["regtype"]]
    if regtype == winreg.REG_DWORD:
        winreg.SetValueEx(key, spec["name"], 0, regtype, int(value))
    else:
        winreg.SetValueEx(key, spec["name"], 0, regtype, str(value))
    winreg.CloseKey(key)


def apply_command(spec, value):
    cmd = spec["template"].format(value=value)
    if not IS_WINDOWS:
        print(f"[dry-run] command: {cmd}")
        return
    subprocess.run(cmd, shell=True, check=False)


def apply_app_block(value):
    """Block listed .exe names using the Image File Execution Options 'Debugger'
    trick, which prevents the executable from launching."""
    exes = [e.strip() for e in value.split(",") if e.strip()]
    base = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
    if not IS_WINDOWS:
        print(f"[dry-run] block apps: {exes}")
        return
    for exe in exes:
        path = f"{base}\\{exe}"
        key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "Debugger", 0, winreg.REG_SZ, "systray.exe")
        winreg.CloseKey(key)


HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts" if IS_WINDOWS else "/etc/hosts"
HOSTS_MARK_BEGIN = "# >>> FleetPanel blocked sites >>>"
HOSTS_MARK_END = "# <<< FleetPanel blocked sites <<<"


def apply_web_block(value):
    """Block listed domains by redirecting them to 0.0.0.0 in the hosts file.
    Adds both the bare domain and its www. form. Managed inside a marked block
    so it can be rewritten cleanly each run without touching other entries."""
    domains = [d.strip().lower().replace("http://", "").replace("https://", "").strip("/")
               for d in value.split(",") if d.strip()]
    lines = [HOSTS_MARK_BEGIN]
    for d in domains:
        lines.append(f"0.0.0.0 {d}")
        if not d.startswith("www."):
            lines.append(f"0.0.0.0 www.{d}")
    lines.append(HOSTS_MARK_END)
    block = "\n".join(lines) + "\n"

    if not IS_WINDOWS:
        print(f"[dry-run] web_block -> hosts file:\n{block.rstrip()}")
        return
    try:
        with open(HOSTS_PATH, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    # strip any previous FleetPanel-managed block, then append the fresh one
    if HOSTS_MARK_BEGIN in content and HOSTS_MARK_END in content:
        pre = content.split(HOSTS_MARK_BEGIN)[0].rstrip("\n")
        post = content.split(HOSTS_MARK_END)[1].lstrip("\n")
        content = (pre + "\n" + post).strip("\n")
    content = content.rstrip("\n") + "\n\n" + block
    with open(HOSTS_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    # flush DNS cache so the block takes effect immediately
    subprocess.run("ipconfig /flushdns", shell=True, check=False)


def apply_policies(policies, catalog):
    """policies: {key: value}; catalog: {key: apply-spec (+type)}"""
    applied = 0
    for key, value in policies.items():
        spec = catalog.get(key)
        if not spec:
            print(f"[agent] unknown policy '{key}', skipping")
            continue
        kind = spec.get("kind")
        try:
            if spec.get("type") == "bool":
                # value is "1"; translate to the 'on' payload
                reg_val = spec.get("on", 1)
                if kind == "registry":
                    apply_registry(spec, reg_val)
            elif kind == "registry":
                apply_registry(spec, value)
            elif kind == "command":
                apply_command(spec, value)
            elif kind == "app_block":
                apply_app_block(value)
            elif kind == "web_block":
                apply_web_block(value)
            applied += 1
        except Exception as e:
            print(f"[agent] failed to apply '{key}': {e}")
    print(f"[agent] applied {applied}/{len(policies)} policies")


# ------------------------------------------------------------------- data roaming
def roaming_dir(username):
    d = os.path.join(HERE, "roaming", username)
    os.makedirs(d, exist_ok=True)
    return d


def sync_down(cfg, token, username):
    status, body = _request(cfg, "GET", f"/api/sync/manifest/{username}", token=token)
    if status != 200:
        print(f"[agent] manifest fetch failed ({status})")
        return
    manifest = json.loads(body)
    d = roaming_dir(username)
    for item in manifest:
        rel = item["relpath"]
        status, data = _request(cfg, "GET", f"/api/sync/download/{username}/{rel}", token=token)
        if status == 200:
            with open(os.path.join(d, rel), "wb") as f:
                f.write(data)
    print(f"[agent] pulled {len(manifest)} roaming file(s) for {username}")


def sync_up(cfg, token, username):
    d = roaming_dir(username)
    count = 0
    for name in os.listdir(d):
        full = os.path.join(d, name)
        if not os.path.isfile(full):
            continue
        with open(full, "rb") as f:
            content = f.read()
        # minimal multipart body
        boundary = "----fleetboundary1234"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        status, _ = _request(cfg, "POST", f"/api/sync/upload/{username}", token=token,
                             raw=body,
                             headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                      "X-Rel-Path": name})
        if status == 200:
            count += 1
    print(f"[agent] pushed {count} roaming file(s) for {username}")


# ------------------------------------------------------- importable session API
# These are used by login_app.py (the full-screen FleetPanel login) as well as
# the CLI main() below. Keeping them here makes the catalog/apply logic the
# single source of truth for both entry points.

def authenticate(cfg, token, username, password):
    """Verify a FleetPanel user against the server.
    Returns the login info dict (user_id, username, display_name, policies,
    catalog) on success, or None on bad credentials."""
    status, body = _request(cfg, "POST", "/api/login", token=token,
                            json_body={"username": username, "password": password})
    if status != 200:
        return None
    return json.loads(body)


def start_session(cfg, token, info):
    """Begin a user's session on this PC: pull their roaming data, then apply
    their effective policies. `info` is what authenticate() returned."""
    sync_down(cfg, token, info["username"])
    apply_policies(info["policies"], info["catalog"])


# ------------------------------------------------------------------- watchdog
# Continuously re-applies (re-checks) the entire registry policy set so that:
#   * policies stay enforced for the whole session, and
#   * if a user edits a value out of the registry, it snaps back within
#     `interval` seconds (self-healing).
# NOTE: this keeps values CORRECT; some HKLM keys (e.g. USBSTOR Start) are only
# read by Windows at boot/driver-load, so their *effect* still needs a reboot —
# but the watchdog guarantees the value can't be silently removed. Requires the
# agent to run as admin/SYSTEM to write HKLM.
import threading as _threading

_watchdog_stop = None
_watchdog_thread = None


def _reapply_quiet(policies, catalog):
    """Re-apply every policy without the chatty per-policy logging."""
    for key, value in policies.items():
        spec = catalog.get(key)
        if not spec:
            continue
        kind = spec.get("kind")
        try:
            if spec.get("type") == "bool" and kind == "registry":
                apply_registry(spec, spec.get("on", 1))
            elif kind == "registry":
                apply_registry(spec, value)
            elif kind == "command":
                apply_command(spec, value)
            elif kind == "app_block":
                apply_app_block(value)
            elif kind == "web_block":
                apply_web_block(value)
        except Exception:
            pass  # stay quiet; try again next tick


def start_watchdog(info, interval=30):
    """Start a background thread that re-checks the whole policy set every
    `interval` seconds until stop_watchdog() is called. Fails safe: never
    raises to the caller, so it can't stall login."""
    global _watchdog_stop, _watchdog_thread
    try:
        stop_watchdog()  # ensure only one running
        policies = (info or {}).get("policies") or {}
        catalog = (info or {}).get("catalog") or {}
        if not policies:
            print("[agent] no policies to watch; watchdog not started")
            return None
        _watchdog_stop = _threading.Event()

        def loop(stop_evt):
            print(f"[agent] watchdog running (re-check every {interval}s, "
                  f"{len(policies)} policies)")
            while not stop_evt.wait(interval):
                try:
                    _reapply_quiet(policies, catalog)
                except Exception:
                    pass  # never let the loop die

        _watchdog_thread = _threading.Thread(target=loop, args=(_watchdog_stop,), daemon=True)
        _watchdog_thread.start()
        return _watchdog_thread
    except Exception as e:
        print(f"[agent] start_watchdog error (ignored): {e}")
        return None


def stop_watchdog():
    """Stop the re-check loop (call on logout)."""
    global _watchdog_stop, _watchdog_thread
    if _watchdog_stop is not None:
        _watchdog_stop.set()
    _watchdog_thread = None
    _watchdog_stop = None


def revert_policies(policies, catalog):
    """Return the machine to the 'off' baseline for the policies that were
    applied, so the next user doesn't inherit the previous user's restrictions.
    For bool registry policies this writes the 'off' value; for web/app blocks
    it clears the managed block/list."""
    for key in policies:
        spec = catalog.get(key)
        if not spec:
            continue
        kind = spec.get("kind")
        try:
            if kind == "registry" and spec.get("type") == "bool":
                apply_registry(spec, spec.get("off", 0))
            elif kind == "web_block":
                apply_web_block("")          # empties the managed hosts block
            elif kind == "app_block":
                _clear_app_block(policies[key])
            # value-type registry / commands are left as-is (no safe generic
            # revert); the next user's start_session overwrites them anyway.
        except Exception as e:
            print(f"[agent] failed to revert '{key}': {e}")


def _clear_app_block(value):
    exes = [e.strip() for e in value.split(",") if e.strip()]
    base = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
    if not IS_WINDOWS:
        print(f"[dry-run] clear app-block: {exes}")
        return
    for exe in exes:
        try:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{exe}")
        except FileNotFoundError:
            pass


def end_session(cfg, token, info):
    """End a user's session: push their roaming data back and revert the
    per-user policies so the PC is clean for the next login."""
    sync_up(cfg, token, info["username"])
    revert_policies(info["policies"], info["catalog"])


def launch_desktop():
    """Start the Windows desktop (Explorer) so the user has a normal session
    after logging into FleetPanel. If Explorer is already running this is a
    no-op. On non-Windows it's a dry-run print."""
    if not IS_WINDOWS:
        print("[dry-run] launch desktop (explorer.exe)")
        return
    try:
        # Only start Explorer if it isn't already the shell/running.
        out = subprocess.run('tasklist /FI "IMAGENAME eq explorer.exe"',
                             shell=True, capture_output=True, text=True)
        if "explorer.exe" not in out.stdout.lower():
            subprocess.Popen("explorer.exe", shell=True)
    except Exception as e:
        print(f"[agent] could not launch desktop: {e}")


def close_desktop():
    """Close the user's desktop/apps for a clean handoff to the next user.
    Stops Explorer (the login app keeps running as its own process)."""
    if not IS_WINDOWS:
        print("[dry-run] close desktop (taskkill explorer.exe)")
        return
    try:
        subprocess.run("taskkill /f /im explorer.exe", shell=True, check=False)
    except Exception as e:
        print(f"[agent] could not close desktop: {e}")


# --------------------------------------------------------------------------- main
def main():
    """CLI entry point (headless / testing). login_app.py is the GUI front end."""
    cfg = load_config()
    token = enroll(cfg)

    username = os.environ.get("FLEET_USER") or input("FleetPanel username: ")
    password = os.environ.get("FLEET_PASS") or getpass.getpass("FleetPanel password: ")

    info = authenticate(cfg, token, username, password)
    if not info:
        sys.exit("[agent] login failed. Check credentials.")
    print(f"[agent] welcome {info.get('display_name') or info['username']}")

    start_session(cfg, token, info)
    print("[agent] session ready. (On logoff, run with --logoff to push data back.)")

    if "--logoff" in sys.argv:
        end_session(cfg, token, info)


if __name__ == "__main__":
    main()
