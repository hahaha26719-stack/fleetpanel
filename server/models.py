"""
Database layer (SQLite, standard library only — no ORM needed for this size).

Schema
------
users          : the managed Windows accounts + the admin(s)
groups         : named collections of users
user_groups    : many-to-many membership
policies       : effective policy values, attached to either a user or a group
                 (scope = 'user' or 'group'). User-scoped values override group.
devices        : known managed PCs (registered by the agent)
sync_files     : metadata for roaming user data (blobs stored on disk)
"""

import os
import sqlite3
import secrets
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get("FLEET_DB", os.path.join(os.path.dirname(__file__), "fleet.db"))
DATA_DIR = os.environ.get("FLEET_DATA", os.path.join(os.path.dirname(__file__), "userdata"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    display_name  TEXT DEFAULT '',
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_groups (
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

CREATE TABLE IF NOT EXISTS policies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scope       TEXT NOT NULL CHECK (scope IN ('user','group')),
    scope_id    INTEGER NOT NULL,
    policy_key  TEXT NOT NULL,
    value       TEXT NOT NULL,
    UNIQUE (scope, scope_id, policy_key)
);

CREATE TABLE IF NOT EXISTS devices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname     TEXT UNIQUE NOT NULL,
    token        TEXT NOT NULL,
    last_seen    TEXT,
    last_user    TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_files (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    relpath    TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    size       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, relpath)
);
"""


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()

    # Seed an admin account on first run.
    cur = conn.execute("SELECT COUNT(*) AS c FROM users WHERE is_admin = 1")
    if cur.fetchone()["c"] == 0:
        temp_pw = secrets.token_urlsafe(12)
        conn.execute(
            "INSERT INTO users (username, display_name, password_hash, is_admin, enabled, created_at) "
            "VALUES (?,?,?,1,1,?)",
            ("admin", "Administrator", generate_password_hash(temp_pw), _now()),
        )
        conn.commit()
        print("=" * 60)
        print(" INITIAL ADMIN CREATED")
        print("   username: admin")
        print(f"   password: {temp_pw}")
        print("   >>> Log in and change this immediately. <<<")
        print("=" * 60)
    conn.close()


# --------------------------------------------------------------------------- users
def create_user(username, password, display_name="", is_admin=False):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, display_name, password_hash, is_admin, enabled, created_at) "
            "VALUES (?,?,?,?,1,?)",
            (username, display_name, generate_password_hash(password), 1 if is_admin else 0, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def verify_login(username, password):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ? AND enabled = 1", (username,)).fetchone()
    conn.close()
    if row and check_password_hash(row["password_hash"], password):
        return dict(row)
    return None


def get_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_name(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_users():
    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY username").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_password(user_id, password):
    conn = get_db()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                 (generate_password_hash(password), user_id))
    conn.commit()
    conn.close()


def set_enabled(user_id, enabled):
    conn = get_db()
    conn.execute("UPDATE users SET enabled = ? WHERE id = ?", (1 if enabled else 0, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# -------------------------------------------------------------------------- groups
def create_group(name, description=""):
    conn = get_db()
    try:
        conn.execute("INSERT INTO groups (name, description, created_at) VALUES (?,?,?)",
                     (name, description, _now()))
        conn.commit()
    finally:
        conn.close()


def list_groups():
    conn = get_db()
    rows = conn.execute("SELECT * FROM groups ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_group(group_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_group(group_id):
    conn = get_db()
    conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()


def set_membership(user_id, group_id, member):
    conn = get_db()
    if member:
        conn.execute("INSERT OR IGNORE INTO user_groups (user_id, group_id) VALUES (?,?)",
                     (user_id, group_id))
    else:
        conn.execute("DELETE FROM user_groups WHERE user_id = ? AND group_id = ?",
                     (user_id, group_id))
    conn.commit()
    conn.close()


def groups_for_user(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT g.* FROM groups g JOIN user_groups ug ON ug.group_id = g.id "
        "WHERE ug.user_id = ? ORDER BY g.name", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def members_of_group(group_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT u.* FROM users u JOIN user_groups ug ON ug.user_id = u.id "
        "WHERE ug.group_id = ? ORDER BY u.username", (group_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------------ policies
def set_policy(scope, scope_id, policy_key, value):
    conn = get_db()
    if value is None or value == "":
        conn.execute("DELETE FROM policies WHERE scope=? AND scope_id=? AND policy_key=?",
                     (scope, scope_id, policy_key))
    else:
        conn.execute(
            "INSERT INTO policies (scope, scope_id, policy_key, value) VALUES (?,?,?,?) "
            "ON CONFLICT(scope, scope_id, policy_key) DO UPDATE SET value=excluded.value",
            (scope, scope_id, policy_key, str(value)))
    conn.commit()
    conn.close()


def get_policies(scope, scope_id):
    conn = get_db()
    rows = conn.execute("SELECT policy_key, value FROM policies WHERE scope=? AND scope_id=?",
                        (scope, scope_id)).fetchall()
    conn.close()
    return {r["policy_key"]: r["value"] for r in rows}


def effective_policies(user_id):
    """Group policies first, then user policies override them."""
    result = {}
    for g in groups_for_user(user_id):
        result.update(get_policies("group", g["id"]))
    result.update(get_policies("user", user_id))
    return result


# ------------------------------------------------------------------------- devices
def register_device(hostname):
    conn = get_db()
    row = conn.execute("SELECT * FROM devices WHERE hostname = ?", (hostname,)).fetchone()
    if row:
        conn.close()
        return dict(row)
    token = secrets.token_urlsafe(24)
    conn.execute("INSERT INTO devices (hostname, token, created_at) VALUES (?,?,?)",
                 (hostname, token, _now()))
    conn.commit()
    row = conn.execute("SELECT * FROM devices WHERE hostname = ?", (hostname,)).fetchone()
    conn.close()
    return dict(row)


def device_by_token(token):
    conn = get_db()
    row = conn.execute("SELECT * FROM devices WHERE token = ?", (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


def touch_device(device_id, last_user):
    conn = get_db()
    conn.execute("UPDATE devices SET last_seen=?, last_user=? WHERE id=?",
                 (_now(), last_user, device_id))
    conn.commit()
    conn.close()


def list_devices():
    conn = get_db()
    rows = conn.execute("SELECT * FROM devices ORDER BY hostname").fetchall()
    conn.close()
    return [dict(r) for r in rows]
