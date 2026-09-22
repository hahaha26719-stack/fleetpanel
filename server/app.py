"""
FleetPanel — Flask web panel + agent REST API.

Run (dev):    python app.py
Run (prod):   gunicorn -w 2 -b 127.0.0.1:8080 app:app   (put nginx+HTTPS in front)
"""

import os
import secrets
import functools

from flask import (Flask, request, redirect, url_for, render_template,
                   session, flash, jsonify, abort, send_file)
from werkzeug.utils import secure_filename

import models
import policies as pol

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLEET_SECRET", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB per sync upload

models.init_db()


# ------------------------------------------------------------------ auth helpers
def current_user():
    uid = session.get("uid")
    return models.get_user(uid) if uid else None


def login_required(f):
    @functools.wraps(f)
    def wrapper(*a, **k):
        if not current_user():
            return redirect(url_for("login"))
        return f(*a, **k)
    return wrapper


def admin_required(f):
    @functools.wraps(f)
    def wrapper(*a, **k):
        u = current_user()
        if not u or not u["is_admin"]:
            abort(403)
        return f(*a, **k)
    return wrapper


@app.context_processor
def inject_user():
    return {"me": current_user()}


# ------------------------------------------------------------------------- panel
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = models.verify_login(request.form["username"], request.form["password"])
        if u and u["is_admin"]:
            session["uid"] = u["id"]
            return redirect(url_for("dashboard"))
        flash("Invalid credentials or not an admin account.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html",
                           users=models.list_users(),
                           groups=models.list_groups(),
                           devices=models.list_devices())


# ------------------------------------------------------------------------- users
@app.route("/users")
@login_required
def users():
    return render_template("users.html", users=models.list_users())


@app.route("/users/create", methods=["POST"])
@admin_required
def users_create():
    username = request.form["username"].strip()
    password = request.form["password"]
    if not username or not password:
        flash("Username and password required.", "error")
        return redirect(url_for("users"))
    try:
        models.create_user(username, password,
                           display_name=request.form.get("display_name", ""),
                           is_admin=bool(request.form.get("is_admin")))
        flash(f"User '{username}' created.", "ok")
    except Exception as e:
        flash(f"Could not create user: {e}", "error")
    return redirect(url_for("users"))


@app.route("/users/<int:uid>", methods=["GET", "POST"])
@login_required
def user_detail(uid):
    user = models.get_user(uid)
    if not user:
        abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "password" and request.form.get("password"):
            models.set_password(uid, request.form["password"])
            flash("Password updated.", "ok")
        elif action == "toggle":
            models.set_enabled(uid, not user["enabled"])
            flash("User enabled state toggled.", "ok")
        elif action == "membership":
            selected = set(map(int, request.form.getlist("groups")))
            for g in models.list_groups():
                models.set_membership(uid, g["id"], g["id"] in selected)
            flash("Group membership updated.", "ok")
        elif action == "policy":
            for p in pol.POLICIES:
                val = _read_policy_form(p)
                models.set_policy("user", uid, p["key"], val)
            flash("User policies saved.", "ok")
        return redirect(url_for("user_detail", uid=uid))

    return render_template("user_detail.html",
                           user=user,
                           all_groups=models.list_groups(),
                           my_groups={g["id"] for g in models.groups_for_user(uid)},
                           categories=pol.categories(),
                           policy_values=models.get_policies("user", uid),
                           effective=models.effective_policies(uid))


@app.route("/users/<int:uid>/delete", methods=["POST"])
@admin_required
def user_delete(uid):
    if uid == current_user()["id"]:
        flash("You cannot delete yourself.", "error")
    else:
        models.delete_user(uid)
        flash("User deleted.", "ok")
    return redirect(url_for("users"))


# ------------------------------------------------------------------------ groups
@app.route("/groups")
@login_required
def groups():
    data = []
    for g in models.list_groups():
        data.append({**g, "members": models.members_of_group(g["id"])})
    return render_template("groups.html", groups=data)


@app.route("/groups/create", methods=["POST"])
@admin_required
def groups_create():
    name = request.form["name"].strip()
    if name:
        try:
            models.create_group(name, request.form.get("description", ""))
            flash(f"Group '{name}' created.", "ok")
        except Exception as e:
            flash(f"Could not create group: {e}", "error")
    return redirect(url_for("groups"))


@app.route("/groups/<int:gid>", methods=["GET", "POST"])
@login_required
def group_detail(gid):
    group = models.get_group(gid)
    if not group:
        abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "members":
            selected = set(map(int, request.form.getlist("members")))
            for u in models.list_users():
                models.set_membership(u["id"], gid, u["id"] in selected)
            flash("Group members updated.", "ok")
        elif action == "policy":
            for p in pol.POLICIES:
                val = _read_policy_form(p)
                models.set_policy("group", gid, p["key"], val)
            flash("Group policies saved — applies to all members.", "ok")
        return redirect(url_for("group_detail", gid=gid))

    member_ids = {m["id"] for m in models.members_of_group(gid)}
    return render_template("group_detail.html",
                           group=group,
                           all_users=models.list_users(),
                           member_ids=member_ids,
                           categories=pol.categories(),
                           policy_values=models.get_policies("group", gid))


@app.route("/groups/<int:gid>/delete", methods=["POST"])
@admin_required
def group_delete(gid):
    models.delete_group(gid)
    flash("Group deleted.", "ok")
    return redirect(url_for("groups"))


def _read_policy_form(p):
    """Translate a submitted form field into a stored policy value."""
    if p["type"] == "bool":
        return "1" if request.form.get(p["key"]) else ""
    return request.form.get(p["key"], "").strip()


# ================================================================= AGENT REST API
def _agent_auth():
    token = request.headers.get("X-Agent-Token", "")
    dev = models.device_by_token(token) if token else None
    if not dev:
        abort(401)
    return dev


@app.route("/api/enroll", methods=["POST"])
def api_enroll():
    """A new PC registers itself and receives a device token.
    NOTE: for production, gate this behind an enrollment secret (see docs)."""
    data = request.get_json(force=True, silent=True) or {}
    hostname = (data.get("hostname") or "").strip()
    enroll_secret = os.environ.get("FLEET_ENROLL_SECRET")
    if enroll_secret and data.get("enroll_secret") != enroll_secret:
        abort(403)
    if not hostname:
        abort(400)
    dev = models.register_device(hostname)
    return jsonify({"device_id": dev["id"], "token": dev["token"]})


@app.route("/api/login", methods=["POST"])
def api_login():
    """A user logs in on a managed PC. Returns their effective policies so the
    agent can apply them, enabling per-user roaming policy."""
    dev = _agent_auth()
    data = request.get_json(force=True, silent=True) or {}
    user = models.verify_login(data.get("username", ""), data.get("password", ""))
    if not user or user["is_admin"]:
        # admins are panel-only; regular users log into PCs
        if not user or user["is_admin"]:
            abort(401)
    models.touch_device(dev["id"], user["username"])
    return jsonify({
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "policies": models.effective_policies(user["id"]),
        "catalog": {p["key"]: p["apply"] | {"type": p["type"]} for p in pol.POLICIES},
    })


@app.route("/api/verify_admin", methods=["POST"])
def api_verify_admin():
    """Used by the agent's admin-only escape hatch (Ctrl+Alt+Q). Confirms that
    the supplied password matches SOME enabled admin account. Optionally a
    username can be supplied to check a specific admin. Returns {"ok": bool}."""
    _agent_auth()
    data = request.get_json(force=True, silent=True) or {}
    password = data.get("password", "")
    username = data.get("username", "").strip()
    if not password:
        return jsonify({"ok": False})
    if username:
        u = models.verify_login(username, password)
        return jsonify({"ok": bool(u and u["is_admin"])})
    # no username: accept if the password matches ANY enabled admin
    for u in models.list_users():
        if u["is_admin"] and u["enabled"]:
            if models.verify_login(u["username"], password):
                return jsonify({"ok": True})
    return jsonify({"ok": False})


@app.route("/api/policies/<username>", methods=["GET"])
def api_policies(username):
    """Agent re-fetches a logged-in user's effective policies (e.g. on refresh)."""
    _agent_auth()
    user = models.get_user_by_name(username)
    if not user:
        abort(404)
    return jsonify({
        "policies": models.effective_policies(user["id"]),
        "catalog": {p["key"]: p["apply"] | {"type": p["type"]} for p in pol.POLICIES},
    })


# ---- roaming data sync (very simple last-write-wins per relpath) --------------
def _user_data_dir(user_id):
    d = os.path.join(models.DATA_DIR, str(user_id))
    os.makedirs(d, exist_ok=True)
    return d


@app.route("/api/sync/manifest/<username>", methods=["GET"])
def api_sync_manifest(username):
    _agent_auth()
    user = models.get_user_by_name(username)
    if not user:
        abort(404)
    conn = models.get_db()
    rows = conn.execute("SELECT relpath, updated_at, size FROM sync_files WHERE user_id=?",
                        (user["id"],)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/sync/upload/<username>", methods=["POST"])
def api_sync_upload(username):
    _agent_auth()
    user = models.get_user_by_name(username)
    if not user:
        abort(404)
    relpath = request.headers.get("X-Rel-Path", "")
    safe = secure_filename(relpath) or "file.bin"
    dest = os.path.join(_user_data_dir(user["id"]), safe)
    request.files["file"].save(dest)
    size = os.path.getsize(dest)
    conn = models.get_db()
    conn.execute(
        "INSERT INTO sync_files (user_id, relpath, updated_at, size) VALUES (?,?,?,?) "
        "ON CONFLICT(user_id, relpath) DO UPDATE SET updated_at=excluded.updated_at, size=excluded.size",
        (user["id"], safe, models._now(), size))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "relpath": safe, "size": size})


@app.route("/api/sync/download/<username>/<path:relpath>", methods=["GET"])
def api_sync_download(username, relpath):
    _agent_auth()
    user = models.get_user_by_name(username)
    if not user:
        abort(404)
    safe = secure_filename(relpath)
    path = os.path.join(_user_data_dir(user["id"]), safe)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=safe)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
