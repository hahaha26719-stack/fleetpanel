"""
FleetPanel Kid Launcher
=======================
Full-screen, child-friendly launcher shown after a kid signs in. Big colourful
tiles for the allowed apps: Notepad, PowerPoint, Edge (our own simplified
versions). Which tiles appear is controlled by the admin 'app_mode' policy.

Launched by login_app.py after a successful login. Also runnable standalone for
testing:  python launcher.py --windowed
"""
import os
import sys
import subprocess
import tkinter as tk

import kidcommon as kc

WINDOWED = "--windowed" in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable  # same python to launch child apps

# app key -> (nice name, emoji, colour, script)
APPS = [
    ("notepad",    "Notepad",    "📝", kc.GREEN,   "kidnotepad.py"),
    ("powerpoint", "Slides",     "📊", kc.PINK,    "kidppt.py"),
    ("edge",       "Web",        "🌐", kc.PRIMARY, "kidbrowser.py"),
]


class Launcher(tk.Tk):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.title("My Apps")
        self.configure(bg=kc.BG)
        if WINDOWED:
            self.geometry("1000x680")
        else:
            self.attributes("-fullscreen", True)
        self.bind("<Escape>", lambda e: self.destroy() if WINDOWED else None)

        name = session.get("display_name") or session.get("username", "friend")
        tk.Label(self, text=f"Hi {name}! 👋", bg=kc.BG, fg=kc.INK,
                 font=(kc.FONT, 34, "bold")).pack(pady=(40, 6))
        tk.Label(self, text="Pick an app to start", bg=kc.BG, fg=kc.MUT,
                 font=(kc.FONT, 18)).pack(pady=(0, 30))

        grid = tk.Frame(self, bg=kc.BG)
        grid.pack(expand=True)

        app_policy = session.get("policies", {}).get("app_mode", "")
        col = 0
        for key, label, emoji, colour, script in APPS:
            if not kc.is_allowed(app_policy, key):
                continue  # hidden by admin policy
            self._tile(grid, label, emoji, colour, script).grid(
                row=0, column=col, padx=22, pady=10)
            col += 1
        if col == 0:
            tk.Label(grid, text="No apps are available.\nAsk your teacher. 🙂",
                     bg=kc.BG, fg=kc.MUT, font=(kc.FONT, 18)).pack()

        # small logout bar at the bottom
        bar = tk.Frame(self, bg=kc.BG)
        bar.pack(side="bottom", pady=24)
        out = tk.Button(bar, text="Sign out", bg=kc.RED, fg="white",
                        command=self.on_signout)
        kc.style_button(out)
        out.pack()

    def _tile(self, parent, label, emoji, colour, script):
        card = tk.Frame(parent, bg=colour, width=230, height=230,
                        highlightthickness=0)
        card.pack_propagate(False)
        btn = tk.Button(card, text=f"{emoji}\n{label}", bg=colour, fg="white",
                        activebackground=colour, activeforeground="white",
                        relief="flat", bd=0, cursor="hand2",
                        font=(kc.FONT, 22, "bold"),
                        command=lambda s=script: self.open_app(s))
        btn.pack(expand=True, fill="both")
        return card

    def open_app(self, script):
        path = os.path.join(HERE, script)
        try:
            subprocess.Popen([PY, path], cwd=HERE)
        except Exception as e:
            tk.messagebox = __import__("tkinter.messagebox", fromlist=["showerror"])
            tk.messagebox.showerror("Oops", f"Couldn't open the app.\n{e}")

    def on_signout(self):
        # Signal login_app (which launched us) to end the session. We write a
        # sentinel file it watches, then close. login_app handles reboot/cleanup.
        try:
            open(os.path.join(HERE, "signout.flag"), "w").close()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    Launcher(kc.load_session()).mainloop()
