"""
Shared helpers + theme for the FleetPanel kid apps (launcher, browser, notepad,
powerpoint). Keeps a child-friendly look consistent and centralises talking to
the Pi server (policies, picture search, collaboration rooms, file roaming).

The current session (server URL, device token, username, policies) is passed to
each app on the command line or via environment, so the apps can run standalone
for testing too.
"""
import os
import sys
import json
import urllib.request
import urllib.parse

# ---- kid-friendly theme (bright, rounded, big) ------------------------------
BG = "#fef6e4"      # warm cream
PANEL = "#ffffff"
INK = "#2d2a32"
MUT = "#8a8694"
PRIMARY = "#5b8cff"
GREEN = "#3ecf8e"
PINK = "#ff6b9d"
YELLOW = "#ffd23f"
PURPLE = "#9b7bff"
RED = "#ff6b6b"
LINE = "#e7e3d8"

FONT = "Comic Sans MS"   # genuinely kid-friendly on Windows; falls back if absent


def load_session():
    """Session info is written by login_app.py to kid_session.json next to the
    apps (server, token, username, display_name, policies). Falls back to env
    vars so an app can be launched/tested on its own."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "kid_session.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {
        "server": os.environ.get("FLEET_SERVER", "").rstrip("/"),
        "token": os.environ.get("FLEET_TOKEN", ""),
        "username": os.environ.get("FLEET_USER", "guest"),
        "display_name": os.environ.get("FLEET_USER", "guest"),
        "policies": {},
    }


def api(session, method, path, json_body=None, timeout=20):
    """Call the Pi server with the device token. Returns (status, parsed-json-or-bytes)."""
    url = session["server"].rstrip("/") + path
    data = None
    headers = {"X-Agent-Token": session.get("token", "")}
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            try:
                return r.status, json.loads(body)
            except Exception:
                return r.status, body
    except Exception as e:
        return 0, {"error": str(e)}


# ---- policy helpers (mirror server/policies.py is_allowed, kept tiny here) ---
def parse_mode(value):
    if not value:
        return ("allow_except", [])
    if ":" in value:
        mode, rest = value.split(":", 1)
    else:
        mode, rest = "block_except", value
    if mode not in ("allow_except", "block_except"):
        mode = "allow_except"
    items = [x.strip().lower() for x in rest.split(",") if x.strip()]
    return (mode, items)


def is_allowed(value, candidate):
    mode, items = parse_mode(value)
    cand = (candidate or "").strip().lower()
    hit = any(it and it in cand for it in items)
    return hit if mode == "block_except" else not hit


def user_files_dir(username):
    here = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(here, "userfiles", username)
    os.makedirs(d, exist_ok=True)
    return d


def style_button(btn):
    """Apply the chunky kid style to a tk.Button."""
    btn.configure(relief="flat", bd=0, cursor="hand2",
                  font=(FONT, 16, "bold"), padx=18, pady=12)
