"""
FleetPanel Login App  (interpretation B)
========================================

A FULL-SCREEN login screen shown on each managed Windows PC. Instead of a
Microsoft/Windows identity, the user logs in with their **FleetPanel account**
(created by the admin in the web panel). On success the agent:

  * pulls the user's roaming data,
  * applies their effective (group + user) policies,

and shows a session screen with a **Log out / Switch user** button. Logging out
pushes the user's data back, reverts the per-user policies, and returns to the
login screen for the next person.

Design notes
------------
* The PC underneath auto-logs-in to ONE generic, locked Windows account (see
  docs/LOGIN-APP.md). This app is that account's shell/startup program, so from
  the user's point of view their identity is their FleetPanel account.
* Accounts are created ONLY by the admin in the panel — there is no self sign-up
  here (the login form has no "register" path).
* Uses Tkinter (bundled with Python). No extra dependencies.

Run:  python login_app.py         (kiosk/full-screen)
      python login_app.py --windowed   (for testing on a normal desktop)
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont

import agent  # our refactored core: authenticate/start_session/end_session/enroll/load_config

WINDOWED = "--windowed" in sys.argv


def agent_mode_allows(mode_value, candidate):
    """Mirror of policies.is_allowed for the embedded launcher: decide whether
    an app key is permitted under an app_mode value."""
    if not mode_value:
        return True
    mode, _, rest = mode_value.partition(":")
    if mode not in ("allow_except", "block_except"):
        mode, rest = "allow_except", mode_value
    items = [x.strip().lower() for x in rest.split(",") if x.strip()]
    hit = any(it and it in candidate.lower() for it in items)
    return hit if mode == "block_except" else not hit

# ---- colours / theme ----
BG = "#0f1220"
CARD = "#1a1f36"
INK = "#e7e9f3"
MUT = "#9aa0b5"
ACC = "#5b8cff"
OK = "#3ecf8e"
ERR = "#ff6b6b"
LINE = "#2a3050"


class FleetLogin(tk.Tk):
    def __init__(self, cfg, token):
        super().__init__()
        self.cfg = cfg
        self.token = token
        self.info = None  # current session's login info

        self.title("FleetPanel")
        self.configure(bg=BG)
        if WINDOWED:
            self.geometry("900x620")
        else:
            self.attributes("-fullscreen", True)
            self.attributes("-topmost", True)
        self.bind("<Escape>", lambda e: self.destroy() if WINDOWED else None)

        # ---- KIOSK LOCK: the kid cannot close the login app ----------------
        # Block the window-close (X) / Alt+F4 / Ctrl+W so a kid can't quit out
        # to the desktop. The ONLY exits are: signing out (reboots), or the
        # admin escape hatch below. Allowed in windowed TEST mode.
        if not WINDOWED:
            self.protocol("WM_DELETE_WINDOW", lambda: self.bell())
            self.bind_all("<Alt-F4>", lambda e: "break")
            self.bind_all("<Control-w>", lambda e: "break")

        # ---- ESCAPE HATCH (ADMIN ONLY, always available) -------------------
        # Ctrl+Alt+Q: prompts for a FleetPanel ADMIN password; only then does it
        # unlock to the desktop. This is the admin's safety net so the kiosk can
        # never permanently trap you. (Ctrl+Alt+Del also always works.)
        self.bind_all("<Control-Alt-q>", self._escape_hatch)
        self.bind_all("<Control-Alt-Q>", self._escape_hatch)

        self.h1 = tkfont.Font(family="Segoe UI", size=26, weight="bold")
        self.h2 = tkfont.Font(family="Segoe UI", size=15)
        self.base = tkfont.Font(family="Segoe UI", size=12)

        # Use pack(expand) + an inner centering frame — more reliable than a
        # bare .place() which can render blank on some Tk builds.
        outer = tk.Frame(self, bg=BG)
        outer.pack(expand=True, fill="both")
        self.container = tk.Frame(outer, bg=BG)
        self.container.place(relx=0.5, rely=0.5, anchor="center")
        self.show_login()
        # Force an initial draw so the window appears INSTANTLY (no desktop peek).
        self.update_idletasks()

        # Do the slow startup work (hosts restore + wipe + enrollment) in the
        # BACKGROUND so the login screen is usable immediately even if the Pi is
        # slow to reach at boot. self.token fills in when enrollment completes.
        self._enroll_done = threading.Event()
        threading.Thread(target=self._background_startup, daemon=True).start()

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
        """ADMIN-ONLY emergency exit (Ctrl+Alt+Q). Prompts for a FleetPanel
        ADMIN password; only if it verifies does it stop the watchdog, revert
        the current user's policies, and drop to the desktop. This is a recovery
        tool for admins — NOT a bypass button for ordinary users."""
        from tkinter import simpledialog, messagebox
        pw = simpledialog.askstring("Admin unlock",
                                    "Enter a FleetPanel ADMIN password to unlock this PC:",
                                    show="•", parent=self)
        if not pw:
            return  # cancelled — stay locked
        # Verify against the server as an ADMIN account (admins are the only
        # ones allowed to unlock). We check via a dedicated admin-verify call.
        ok = self._verify_admin(pw)
        if not ok:
            messagebox.showerror("Admin unlock", "Incorrect admin password.", parent=self)
            return
        # Authorised: tear down restrictions and hand over the desktop.
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
        """Ask the server to confirm this is a valid ADMIN password (any admin
        account). Returns True/False. Fails closed on error."""
        try:
            return agent.verify_admin(self.cfg, self.token, password)
        except Exception:
            return False

    # ------------------------------------------------------------- login screen
    def show_login(self, message=None, is_error=False):
        self.info = None
        for w in self.container.winfo_children():
            w.destroy()

        card = tk.Frame(self.container, bg=CARD, padx=48, pady=40,
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
                                   activeforeground="white", cursor="hand2",
                                   command=self.on_login)
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
        # network work off the UI thread
        threading.Thread(target=self._do_login, args=(username, password), daemon=True).start()

    def _do_login(self, username, password):
        # Make sure enrollment has finished (it runs in the background at
        # startup). Wait up to ~20s; if the token still isn't there, try once
        # more now so the kid gets a clear result instead of a silent failure.
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
        self.after(0, lambda: self._loading_session(info))

    def _loading_session(self, info):
        for w in self.container.winfo_children():
            w.destroy()
        card = tk.Frame(self.container, bg=CARD, padx=48, pady=40)
        card.pack()
        tk.Label(card, text="Setting up your session…", font=self.h1, fg=INK, bg=CARD).pack()
        tk.Label(card, text="Loading your files and applying your settings.",
                 font=self.h2, fg=MUT, bg=CARD).pack(pady=(6, 0))
        threading.Thread(target=self._start_session, args=(info,), daemon=True).start()

    def _start_session(self, info):
        # Core session setup (roaming + policies). If this fails, back to login.
        try:
            agent.start_session(self.cfg, self.token, info)
        except Exception as e:
            self.after(0, lambda: self.show_login(f"Session error: {e}", is_error=True))
            return

        # Non-critical setup — never let these stall the login.
        try:
            agent.backup_hosts()                      # pristine hosts for later restore
        except Exception as e:
            print(f"[agent] hosts backup skipped: {e}")
        try:
            agent.write_kid_session(self.cfg, self.token, info)  # for the kid apps
        except Exception as e:
            print(f"[agent] kid session write failed: {e}")
        try:
            agent.start_watchdog(info, interval=30)
        except Exception as e:
            print(f"[agent] watchdog failed to start (continuing): {e}")

        # Show the LAUNCHER as the homepage, in THIS SAME window (bundled —
        # no separate launcher process).
        self.after(0, lambda: self.show_launcher(info))

    def _launcher_exe(self):
        """Use pythonw.exe (no console window) so there's no console to close."""
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            cand = exe[:-len("python.exe")] + "pythonw.exe"
            if os.path.exists(cand):
                return cand
        return exe

    # ======================================================= EMBEDDED LAUNCHER
    # The launcher is the "homepage" shown in THIS window after login — bundled,
    # not a separate process. Big tiles for the allowed apps; the apps
    # themselves still open as their own windows.
    def show_launcher(self, info):
        import subprocess
        self.info = info
        self._session_active = True
        for w in self.container.winfo_children():
            w.destroy()

        # The three apps: key -> (label, emoji, colour, script)
        APPS = [
            ("notepad",    "Notepad", "📝", "#3ecf8e", "kidnotepad.py"),
            ("powerpoint", "Slides",  "📊", "#ff6b9d", "kidppt.py"),
            ("edge",       "Web",     "🌐", "#5b8cff", "kidbrowser.py"),
        ]

        name = info.get("display_name") or info.get("username", "friend")
        tk.Label(self.container, text=f"Hi {name}! 👋", bg=BG, fg=INK,
                 font=("Comic Sans MS", 30, "bold")).pack(pady=(10, 2))
        tk.Label(self.container, text="Pick an app to start", bg=BG, fg=MUT,
                 font=("Comic Sans MS", 16)).pack(pady=(0, 24))

        grid = tk.Frame(self.container, bg=BG)
        grid.pack()
        app_policy = info.get("policies", {}).get("app_mode", "")
        here = os.path.dirname(os.path.abspath(__file__))
        col = 0
        for key, label, emoji, colour, script in APPS:
            if not agent_mode_allows(app_policy, key):
                continue
            card = tk.Frame(grid, bg=colour, width=200, height=200)
            card.pack_propagate(False)
            tk.Button(card, text=f"{emoji}\n{label}", bg=colour, fg="white",
                      activebackground=colour, activeforeground="white",
                      relief="flat", bd=0, cursor="hand2",
                      font=("Comic Sans MS", 20, "bold"),
                      command=lambda s=script: self._open_app(s)
                      ).pack(expand=True, fill="both")
            card.grid(row=0, column=col, padx=18, pady=10)
            col += 1
        if col == 0:
            tk.Label(grid, text="No apps are available.\nAsk your teacher. 🙂",
                     bg=BG, fg=MUT, font=("Comic Sans MS", 16)).pack()

        out = tk.Button(self.container, text="Sign out", bg=ERR, fg="white",
                        relief="flat", bd=0, cursor="hand2",
                        font=("Comic Sans MS", 15, "bold"), padx=18, pady=10,
                        command=self.on_logout)
        out.pack(pady=28)

    def _open_app(self, script):
        import subprocess
        here = os.path.dirname(os.path.abspath(__file__))
        exe = self._launcher_exe()
        args = [exe, os.path.join(here, script)]
        if WINDOWED:
            args.append("--windowed")
        try:
            proc = subprocess.Popen(args, cwd=here)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Oops", f"Couldn't open the app.\n{e}")
            return
        # Stay full-screen as the backdrop; just drop topmost so the app shows.
        try:
            if not WINDOWED:
                self.attributes("-topmost", False)
        except Exception:
            pass
        self._watch_app(proc)

    def _watch_app(self, proc):
        # When the app closes, bring this window (the launcher) back to front.
        if proc.poll() is None:
            self.after(600, lambda: self._watch_app(proc))
        else:
            try:
                if not WINDOWED:
                    self.attributes("-topmost", True)
                    self.lift()
                    self.focus_force()
                    self.after(400, lambda: self.attributes("-topmost", False))
            except Exception:
                pass

    def on_logout(self):
        # Replace the launcher with a "signing out" message in-window.
        for w in self.container.winfo_children():
            w.destroy()
        tk.Label(self.container, text="Signing out…", font=self.h1, fg=INK, bg=BG).pack(pady=40)
        self._logout_msg = tk.Label(self.container, text="Saving your files…",
                                    font=self.base, fg=MUT, bg=BG)
        self._logout_msg.pack()
        threading.Thread(target=self._do_logout, daemon=True).start()

    def _do_logout(self):
        try:
            self._session_active = False
            agent.stop_watchdog()
            agent.end_session(self.cfg, self.token, self.info)  # push files + revert policies
            agent.clear_kid_session()
        except Exception as e:
            self.after(0, lambda: self._logout_msg.config(text=f"Logout error: {e}", fg=ERR))
            return
        # Sign-out => REBOOT. On next boot, startup_cleanup() restores hosts and
        # wipes local data for a clean slate. (In windowed test mode we skip the
        # reboot and just return to the login screen.)
        if WINDOWED:
            self.after(0, self._back_to_login)
        else:
            self.after(0, lambda: self._logout_msg.config(text="Signing out and restarting…"))
            agent.reboot()

    def _back_to_login(self):
        # restore the full-screen login for the next user
        try:
            self.deiconify()
            if not WINDOWED:
                self.attributes("-fullscreen", True)
                self.attributes("-topmost", True)
        except Exception:
            pass
        self.show_login("You have been signed out.", is_error=False)


def build():
    cfg = agent.load_config()
    # Show the window IMMEDIATELY (token comes in the background) so the desktop
    # never shows and there's no ~1 min wait if the network/Pi is slow at boot.
    win = FleetLogin(cfg, token="")
    return win


if __name__ == "__main__":
    build().mainloop()
