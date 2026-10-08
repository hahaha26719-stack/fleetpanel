"""
FleetPanel Launcher  (login + home screen + taskbar, all in one)
================================================================

This single app is the kiosk SHELL. It:
  1. Shows the FleetPanel LOGIN first (admin-created accounts only).
  2. After login, becomes the HOME SCREEN — a full-screen desktop-like backdrop
     with app tiles and an Explorer-style BOTTOM TASKBAR.
  3. Opens the kid apps (Notepad / Slides / Web) as their own resizable windows
     (they keep normal minimize / maximize / close controls — the "tray").
     Minimizing an app returns you to the home screen underneath.
  4. The taskbar shows open apps (click to raise), a clock, and Sign out.

Set as the kiosk user's shell:
    HKCU\...\Winlogon\Shell = pythonw C:\FleetAgent\launcher.py

Test:  python launcher.py --windowed
"""

import os
import sys
import time
import threading
import subprocess
import tkinter as tk
from tkinter import font as tkfont

import agent  # enroll/authenticate/start_session/end_session/policies/etc.

WINDOWED = "--windowed" in sys.argv

# ---- theme ----
BG = "#0f1220"
CARD = "#1a1f36"
INK = "#e7e9f3"
MUT = "#9aa0b5"
ACC = "#5b8cff"
OK = "#3ecf8e"
ERR = "#ff6b6b"
LINE = "#2a3050"
BAR = "#141829"   # taskbar colour

# app key -> (label, emoji, colour, script)
APPS = [
    ("notepad",    "Notepad", "📝", "#3ecf8e", "kidnotepad.py"),
    ("powerpoint", "Slides",  "📊", "#ff6b9d", "kidppt.py"),
    ("edge",       "Web",     "🌐", "#5b8cff", "kidbrowser.py"),
]


def mode_allows(mode_value, candidate):
    """Decide whether an app key is permitted under an app_mode policy value."""
    if not mode_value:
        return True
    mode, _, rest = mode_value.partition(":")
    if mode not in ("allow_except", "block_except"):
        mode, rest = "allow_except", mode_value
    items = [x.strip().lower() for x in rest.split(",") if x.strip()]
    hit = any(it and it in candidate.lower() for it in items)
    return hit if mode == "block_except" else not hit


class Fleet(tk.Tk):
    def __init__(self, cfg, token=""):
        super().__init__()
        self.cfg = cfg
        self.token = token
        self.info = None
        self._session_active = False
        self._open = []   # list of {"name":.., "proc":.., "btn":..}

        self.title("FleetPanel")
        self.configure(bg=BG)
        if WINDOWED:
            self.geometry("1000x680")
        else:
            self.attributes("-fullscreen", True)
            self.attributes("-topmost", True)
        self.bind("<Escape>", lambda e: self.destroy() if WINDOWED else None)

        if not WINDOWED:
            self.protocol("WM_DELETE_WINDOW", lambda: self.bell())
            self.bind_all("<Alt-F4>", lambda e: "break")
            self.bind_all("<Control-w>", lambda e: "break")
        self.bind_all("<Control-Alt-q>", self._escape_hatch)
        self.bind_all("<Control-Alt-Q>", self._escape_hatch)

        self.h1 = tkfont.Font(family="Segoe UI", size=26, weight="bold")
        self.h2 = tkfont.Font(family="Segoe UI", size=15)
        self.base = tkfont.Font(family="Segoe UI", size=12)

        self.container = tk.Frame(self, bg=BG)   # fills everything above taskbar
        self.container.pack(expand=True, fill="both")
        self.taskbar = None

        self.show_login()
        self.update_idletasks()

        self._enroll_done = threading.Event()
        threading.Thread(target=self._background_startup, daemon=True).start()

    # ----------------------------------------------------------- startup/admin
    def _background_startup(self):
        try:
            agent.startup_cleanup()
        except Exception as e:
            print(f"[agent] startup cleanup skipped: {e}")
        try:
            self.token = agent.enroll(self.cfg)
        except Exception as e:
            print(f"[agent] enroll failed (will retry on login): {e}")
            self.token = ""
        self._enroll_done.set()

    def _escape_hatch(self, event=None):
        from tkinter import simpledialog, messagebox
        pw = simpledialog.askstring("Admin unlock",
                                    "Enter a FleetPanel ADMIN password to unlock this PC:",
                                    show="•", parent=self)
        if not pw:
            return
        if not self._verify_admin(pw):
            messagebox.showerror("Admin unlock", "Incorrect admin password.", parent=self)
            return
        try:
            agent.stop_watchdog()
        except Exception:
            pass
        try:
            if self.info:
                agent.revert_policies(self.info.get("policies", {}), self.info.get("catalog", {}))
        except Exception:
            pass
        try:
            agent.launch_desktop()
        except Exception:
            pass
        self.destroy()

    def _verify_admin(self, password):
        try:
            return agent.verify_admin(self.cfg, self.token, password)
        except Exception:
            return False

    def _clear_container(self):
        for w in self.container.winfo_children():
            w.destroy()

    def _remove_taskbar(self):
        if self.taskbar is not None:
            self.taskbar.destroy()
            self.taskbar = None

    # ----------------------------------------------------------- login screen
    def show_login(self, message=None, is_error=False):
        self.info = None
        self._remove_taskbar()
        self._clear_container()
        center = tk.Frame(self.container, bg=BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(center, bg=CARD, padx=48, pady=40,
                        highlightbackground=LINE, highlightthickness=1)
        card.pack()
        tk.Label(card, text="🛡  FleetPanel", font=self.h1, fg=INK, bg=CARD).pack(anchor="w")
        tk.Label(card, text="Sign in with your FleetPanel account",
                 font=self.h2, fg=MUT, bg=CARD).pack(anchor="w", pady=(2, 22))

        tk.Label(card, text="Username", font=self.base, fg=MUT, bg=CARD).pack(anchor="w")
        self.user_entry = tk.Entry(card, font=self.h2, width=26, bg="#0e122a", fg=INK,
                                   insertbackground=INK, relief="flat", highlightthickness=1,
                                   highlightbackground=LINE, highlightcolor=ACC)
        self.user_entry.pack(pady=(4, 14), ipady=8, fill="x")

        tk.Label(card, text="Password", font=self.base, fg=MUT, bg=CARD).pack(anchor="w")
        self.pass_entry = tk.Entry(card, font=self.h2, width=26, show="•", bg="#0e122a", fg=INK,
                                   insertbackground=INK, relief="flat", highlightthickness=1,
                                   highlightbackground=LINE, highlightcolor=ACC)
        self.pass_entry.pack(pady=(4, 18), ipady=8, fill="x")

        self.msg = tk.Label(card, text=message or "", font=self.base,
                            fg=(ERR if is_error else MUT), bg=CARD, wraplength=340, justify="left")
        self.msg.pack(anchor="w", pady=(0, 10))

        self.login_btn = tk.Button(card, text="Sign in", font=self.h2, bg=ACC, fg="white",
                                   relief="flat", activebackground="#4678e6",
                                   activeforeground="white", cursor="hand2", command=self.on_login)
        self.login_btn.pack(fill="x", ipady=8)
        self.user_entry.focus_set()
        self.pass_entry.bind("<Return>", lambda e: self.on_login())
        self.user_entry.bind("<Return>", lambda e: self.pass_entry.focus_set())

    def on_login(self):
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()
        if not username or not password:
            self.msg.config(text="Enter your username and password.", fg=ERR)
            return
        self.login_btn.config(state="disabled", text="Signing in…")
        self.msg.config(text="Authenticating…", fg=MUT)
        threading.Thread(target=self._do_login, args=(username, password), daemon=True).start()

    def _do_login(self, username, password):
        self._enroll_done.wait(timeout=20)
        if not self.token:
            try:
                self.token = agent.enroll(self.cfg)
            except Exception:
                self.token = ""
        if not self.token:
            self.after(0, lambda: self.show_login(
                "Can't reach the server. Please tell your teacher.", is_error=True))
            return
        info = agent.authenticate(self.cfg, self.token, username, password)
        if not info:
            self.after(0, lambda: self.show_login("Invalid username or password.", is_error=True))
            return
        self.after(0, lambda: self._loading(info))

    def _loading(self, info):
        self._clear_container()
        center = tk.Frame(self.container, bg=BG)
        center.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(center, text="Setting up your session…", font=self.h1, fg=INK, bg=BG).pack()
        tk.Label(center, text="Loading your files and applying your settings.",
                 font=self.h2, fg=MUT, bg=BG).pack(pady=(6, 0))
        threading.Thread(target=self._start_session, args=(info,), daemon=True).start()

    def _start_session(self, info):
        try:
            agent.start_session(self.cfg, self.token, info)
        except Exception as e:
            self.after(0, lambda: self.show_login(f"Session error: {e}", is_error=True))
            return
        for fn, label in [(lambda: agent.backup_hosts(), "hosts backup"),
                          (lambda: agent.write_kid_session(self.cfg, self.token, info), "kid session"),
                          (lambda: agent.start_watchdog(info, interval=30), "watchdog")]:
            try:
                fn()
            except Exception as e:
                print(f"[agent] {label} skipped: {e}")
        self.after(0, lambda: self.show_home(info))

    def _launcher_exe(self):
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            cand = exe[:-len("python.exe")] + "pythonw.exe"
            if os.path.exists(cand):
                return cand
        return exe

    # =============================================================== HOME + TASKBAR
    def show_home(self, info):
        self.info = info
        self._session_active = True
        self._clear_container()

        name = info.get("display_name") or info.get("username", "friend")
        tk.Label(self.container, text=f"Hi {name}! 👋", bg=BG, fg=INK,
                 font=("Comic Sans MS", 30, "bold")).pack(pady=(40, 2))
        tk.Label(self.container, text="Pick an app to start", bg=BG, fg=MUT,
                 font=("Comic Sans MS", 16)).pack(pady=(0, 30))

        grid = tk.Frame(self.container, bg=BG)
        grid.pack(expand=True)
        app_policy = info.get("policies", {}).get("app_mode", "")
        col = 0
        for key, label, emoji, colour, script in APPS:
            if not mode_allows(app_policy, key):
                continue
            card = tk.Frame(grid, bg=colour, width=200, height=200)
            card.pack_propagate(False)
            tk.Button(card, text=f"{emoji}\n{label}", bg=colour, fg="white",
                      activebackground=colour, activeforeground="white",
                      relief="flat", bd=0, cursor="hand2",
                      font=("Comic Sans MS", 20, "bold"),
                      command=lambda s=script, l=label, e=emoji: self._open_app(s, l, e)
                      ).pack(expand=True, fill="both")
            card.grid(row=0, column=col, padx=18, pady=10)
            col += 1
        if col == 0:
            tk.Label(grid, text="No apps are available.\nAsk your teacher. 🙂",
                     bg=BG, fg=MUT, font=("Comic Sans MS", 16)).pack()

        self._build_taskbar()

    def _build_taskbar(self):
        self._remove_taskbar()
        self.taskbar = tk.Frame(self, bg=BAR, height=52)
        self.taskbar.pack(side="bottom", fill="x")
        self.taskbar.pack_propagate(False)

        # left: a little "home" badge
        tk.Label(self.taskbar, text="🏠 Home", bg=BAR, fg=INK,
                 font=("Segoe UI", 12, "bold"), padx=14).pack(side="left")

        # middle: buttons for open apps (filled in by _refresh_taskbar)
        self.task_apps = tk.Frame(self.taskbar, bg=BAR)
        self.task_apps.pack(side="left", padx=10)

        # right: clock + sign out + (admin) update
        out = tk.Button(self.taskbar, text="Sign out", bg=ERR, fg="white", relief="flat",
                        bd=0, cursor="hand2", font=("Segoe UI", 11, "bold"), padx=14,
                        command=self.on_logout)
        out.pack(side="right", padx=10, pady=8)
        upd = tk.Button(self.taskbar, text="⟳ Update", bg=BAR, fg=MUT, relief="flat",
                        bd=0, cursor="hand2", font=("Segoe UI", 10), padx=8,
                        activebackground=BAR, activeforeground=INK,
                        command=self._admin_update)
        upd.pack(side="right", padx=4, pady=8)
        self.clock = tk.Label(self.taskbar, text="", bg=BAR, fg=MUT, font=("Segoe UI", 11), padx=12)
        self.clock.pack(side="right")
        self._tick_clock()
        self._refresh_taskbar()

    def _admin_update(self):
        """Admin-gated in-app updater: verify an admin password, then pull the
        latest app files from GitHub into this folder. No command line needed."""
        from tkinter import simpledialog, messagebox
        pw = simpledialog.askstring("Update", "Enter a FleetPanel ADMIN password to update:",
                                    show="•", parent=self)
        if not pw:
            return
        if not self._verify_admin(pw):
            messagebox.showerror("Update", "Incorrect admin password.", parent=self)
            return
        self._set_update_status("Updating… ⟳")
        threading.Thread(target=self._do_update, daemon=True).start()

    def _set_update_status(self, text):
        try:
            self.clock.config(text=text)
        except Exception:
            pass

    def _do_update(self):
        import urllib.request
        here = os.path.dirname(os.path.abspath(__file__))
        raw = "https://raw.githubusercontent.com/hahaha26719-stack/fleetpanel/main/agent"
        files = ["agent.py", "kidcommon.py", "launcher.py", "kidnotepad.py",
                 "kidppt.py", "kidbrowser.py"]
        ok = 0
        for f in files:
            try:
                req = urllib.request.Request(f"{raw}/{f}", headers={"User-Agent": "FleetPanel"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read()
                with open(os.path.join(here, f), "wb") as out:
                    out.write(data)
                ok += 1
            except Exception as e:
                print(f"[update] {f} failed: {e}")
        from tkinter import messagebox
        def done():
            self._set_update_status("")
            self._tick_clock()
            messagebox.showinfo("Update",
                                f"Updated {ok}/{len(files)} files.\n"
                                "Sign out and back in to use the new version.",
                                parent=self)
        self.after(0, done)

    def _tick_clock(self):
        try:
            self.clock.config(text=time.strftime("%I:%M %p"))
            self.after(10000, self._tick_clock)
        except Exception:
            pass

    def _refresh_taskbar(self):
        # Rebuild the open-apps buttons; drop ones whose process has exited.
        if self.taskbar is None:
            return
        self._open = [o for o in self._open if o["proc"].poll() is None]
        for w in self.task_apps.winfo_children():
            w.destroy()
        for o in self._open:
            b = tk.Button(self.task_apps, text=f"{o['emoji']} {o['name']}",
                          bg=CARD, fg=INK, relief="flat", bd=0, cursor="hand2",
                          font=("Segoe UI", 11), padx=12, pady=6,
                          command=lambda p=o: self._raise_app(p))
            b.pack(side="left", padx=4, pady=7)
        self.after(1200, self._refresh_taskbar)

    def _raise_app(self, o):
        """Restore + bring the app's window to the front (real taskbar behavior).
        Finds the top-level window(s) owned by the app's process and uses the
        Win32 API to un-minimize and foreground it."""
        # Drop our own topmost first so the app can actually come forward.
        try:
            if not WINDOWED:
                self.attributes("-topmost", False)
        except Exception:
            pass
        pid = None
        try:
            pid = o["proc"].pid
        except Exception:
            return
        if os.name != "nt":
            return  # Win32-only; on test boxes there's nothing to raise
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            SW_RESTORE = 9

            EnumWindows = user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            GetWindowThreadProcessId = user32.GetWindowThreadProcessId
            IsWindowVisible = user32.IsWindowVisible

            targets = []

            def _cb(hwnd, lparam):
                wpid = wintypes.DWORD()
                GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
                if wpid.value == pid and IsWindowVisible(hwnd):
                    targets.append(hwnd)
                return True

            EnumWindows(EnumWindowsProc(_cb), 0)
            for hwnd in targets:
                user32.ShowWindow(hwnd, SW_RESTORE)   # un-minimize
                user32.SetForegroundWindow(hwnd)      # bring to front
        except Exception as e:
            print(f"[launcher] could not raise app window: {e}")

    def _open_app(self, script, label, emoji):
        here = os.path.dirname(os.path.abspath(__file__))
        args = [self._launcher_exe(), os.path.join(here, script)]
        if WINDOWED:
            args.append("--windowed")
        try:
            proc = subprocess.Popen(args, cwd=here)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Oops", f"Couldn't open the app.\n{e}")
            return
        self._open.append({"name": label, "emoji": emoji, "proc": proc})
        try:
            if not WINDOWED:
                self.attributes("-topmost", False)   # let the app sit on top
        except Exception:
            pass
        self._refresh_taskbar()

    # ------------------------------------------------------------------ logout
    def on_logout(self):
        self._remove_taskbar()
        self._clear_container()
        center = tk.Frame(self.container, bg=BG)
        center.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(center, text="Signing out…", font=self.h1, fg=INK, bg=BG).pack(pady=10)
        self._logout_msg = tk.Label(center, text="Saving your files…",
                                    font=self.base, fg=MUT, bg=BG)
        self._logout_msg.pack()
        threading.Thread(target=self._do_logout, daemon=True).start()

    def _do_logout(self):
        try:
            self._session_active = False
            agent.stop_watchdog()
            agent.end_session(self.cfg, self.token, self.info)
            agent.clear_kid_session()
        except Exception as e:
            self.after(0, lambda: self._logout_msg.config(text=f"Logout error: {e}", fg=ERR))
            return
        if WINDOWED:
            self.after(0, lambda: self.show_login("You have been signed out."))
        else:
            self.after(0, lambda: self._logout_msg.config(text="Signing out and restarting…"))
            agent.reboot()


def build():
    cfg = agent.load_config()
    return Fleet(cfg, token="")


if __name__ == "__main__":
    build().mainloop()
