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

import sys
import threading
import tkinter as tk
from tkinter import font as tkfont

import agent  # our refactored core: authenticate/start_session/end_session/enroll/load_config

WINDOWED = "--windowed" in sys.argv

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

        # ---- ESCAPE HATCH (always available, even full-screen) --------------
        # Ctrl+Alt+Q: emergency exit — closes the login app and opens the
        # desktop so an admin can always get in. This is your safety net so the
        # kiosk can never fully trap you. (Ctrl+Alt+Del also always works.)
        self.bind_all("<Control-Alt-q>", self._escape_hatch)
        self.bind_all("<Control-Alt-Q>", self._escape_hatch)

        self.h1 = tkfont.Font(family="Segoe UI", size=26, weight="bold")
        self.h2 = tkfont.Font(family="Segoe UI", size=15)
        self.base = tkfont.Font(family="Segoe UI", size=12)

        self.container = tk.Frame(self, bg=BG)
        self.container.place(relx=0.5, rely=0.5, anchor="center")
        self.show_login()

    def _escape_hatch(self, event=None):
        """Emergency exit for admins: stop the watchdog, open the desktop, and
        close the login app so you can never be locked out. Bound to Ctrl+Alt+Q."""
        try:
            agent.stop_watchdog()
        except Exception:
            pass
        try:
            agent.launch_desktop()
        except Exception:
            pass
        self.destroy()

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
        try:
            agent.start_session(self.cfg, self.token, info)
        except Exception as e:
            self.after(0, lambda: self.show_login(f"Session error: {e}", is_error=True))
            return
        # Start the watchdog so policies stay enforced / self-heal all session.
        agent.start_watchdog(info, interval=10)
        # Launch the Windows desktop (Explorer) so the user has a usable session,
        # then step the login app aside.
        agent.launch_desktop()
        self.after(0, lambda: self.show_session(info))

    # ----------------------------------------------------------- session screen
    def show_session(self, info):
        self.info = info
        for w in self.container.winfo_children():
            w.destroy()

        card = tk.Frame(self.container, bg=CARD, padx=48, pady=40,
                        highlightbackground=LINE, highlightthickness=1)
        card.pack()
        name = info.get("display_name") or info["username"]
        tk.Label(card, text=f"Welcome, {name}", font=self.h1, fg=INK, bg=CARD).pack(anchor="w")
        tk.Label(card, text=f"Signed in as {info['username']}. Your policies and data are active.",
                 font=self.h2, fg=MUT, bg=CARD).pack(anchor="w", pady=(4, 8))

        n = len(info.get("policies", {}))
        tk.Label(card, text=f"{n} polic{'y' if n == 1 else 'ies'} applied. Your desktop is ready.",
                 font=self.base, fg=OK, bg=CARD).pack(anchor="w", pady=(0, 22))

        self.status = tk.Label(card, text="", font=self.base, fg=MUT, bg=CARD)
        self.status.pack(anchor="w", pady=(0, 8))

        tk.Label(card, text="Use the desktop normally. Come back to this window\n"
                            "(check the taskbar) and click below when you're done.",
                 font=self.base, fg=MUT, bg=CARD, justify="left").pack(anchor="w", pady=(0, 12))

        logout = tk.Button(card, text="Log out / Switch user", font=self.h2, bg=ERR, fg="white",
                           relief="flat", activebackground="#e05555", activeforeground="white",
                           cursor="hand2", command=self.on_logout)
        logout.pack(fill="x", ipady=8)

        # Step aside so the user can actually use the desktop: leave full-screen
        # and minimize. The window stays available on the taskbar to log out.
        try:
            self.attributes("-fullscreen", False)
            self.attributes("-topmost", False)
            self.iconify()
        except Exception:
            pass

    def on_logout(self):
        self.status.config(text="Saving your files and cleaning up…")
        threading.Thread(target=self._do_logout, daemon=True).start()

    def _do_logout(self):
        try:
            agent.stop_watchdog()   # stop re-applying this user's policies
            agent.end_session(self.cfg, self.token, self.info)
            agent.close_desktop()   # close the user's apps/desktop for a clean handoff
        except Exception as e:
            self.after(0, lambda: self.status.config(text=f"Logout error: {e}", fg=ERR))
            return
        self.after(0, self._back_to_login)

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
    token = agent.enroll(cfg)
    return FleetLogin(cfg, token)


if __name__ == "__main__":
    build().mainloop()
