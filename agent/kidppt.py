"""
FleetPanel Kid Slides (simplified PowerPoint)
=============================================
A very simple slide maker for kids:
  * Add / delete slides, each with a Title and some Text.
  * Navigate slides, big friendly preview.
  * Save / open locally (roams via login_app).
  * "Together" tab: collaborate on the deck using a room code (synced via Pi).

Standalone test:  python kidppt.py --windowed
"""
import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import kidcommon as kc

HERE = os.path.dirname(os.path.abspath(__file__))


class KidSlides(tk.Tk):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.title("Slides")
        self.configure(bg=kc.BG)
        self.geometry("1000x700")
        self.slides = [{"title": "My First Slide", "body": "Type here!"}]
        self.index = 0
        self.current_file = None
        self.room_code = None
        self.room_version = 0
        self.room_poll = None

        tk.Label(self, text="📊 My Slides", bg=kc.BG, fg=kc.INK,
                 font=(kc.FONT, 22, "bold")).pack(pady=(14, 6))
        nb = ttk.Notebook(self)
        nb.pack(expand=True, fill="both", padx=14, pady=10)
        self.nb = nb
        self._build_editor(nb)
        self._build_together(nb)
        self._load_slide()

    # ----------------------------------------------------------- editor tab
    def _build_editor(self, nb):
        f = tk.Frame(nb, bg=kc.PANEL)
        nb.add(f, text="  📊 Slides  ")

        bar = tk.Frame(f, bg=kc.PANEL)
        bar.pack(fill="x", padx=10, pady=10)
        for txt, col, cmd in [("◀", kc.PRIMARY, self.prev_slide),
                              ("▶", kc.PRIMARY, self.next_slide),
                              ("➕ Add", kc.GREEN, self.add_slide),
                              ("🗑 Delete", kc.RED, self.del_slide),
                              ("💾 Save", kc.YELLOW, self.save_file),
                              ("📂 Open", kc.PURPLE, self.open_file)]:
            b = tk.Button(bar, text=txt, bg=col, fg="white", command=cmd)
            kc.style_button(b)
            b.pack(side="left", padx=4)
        self.counter = tk.Label(bar, text="", bg=kc.PANEL, fg=kc.MUT,
                                font=(kc.FONT, 14))
        self.counter.pack(side="right", padx=10)

        body = tk.Frame(f, bg=kc.PANEL)
        body.pack(expand=True, fill="both", padx=10, pady=10)
        tk.Label(body, text="Title", bg=kc.PANEL, fg=kc.MUT,
                 font=(kc.FONT, 13)).pack(anchor="w")
        self.title_entry = tk.Entry(body, font=(kc.FONT, 20, "bold"), bg="white",
                                    fg=kc.INK, relief="flat")
        self.title_entry.pack(fill="x", ipady=8, pady=(0, 12))
        self.title_entry.bind("<KeyRelease>", lambda e: self._store_slide())
        tk.Label(body, text="Text", bg=kc.PANEL, fg=kc.MUT,
                 font=(kc.FONT, 13)).pack(anchor="w")
        self.body_text = tk.Text(body, font=(kc.FONT, 16), wrap="word", bg="white",
                                fg=kc.INK, relief="flat", height=12, padx=10, pady=8)
        self.body_text.pack(expand=True, fill="both")
        self.body_text.bind("<KeyRelease>", lambda e: self._store_slide())

    def _load_slide(self):
        s = self.slides[self.index]
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, s["title"])
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", s["body"])
        self.counter.config(text=f"Slide {self.index + 1} of {len(self.slides)}")

    def _store_slide(self):
        self.slides[self.index] = {"title": self.title_entry.get(),
                                   "body": self.body_text.get("1.0", "end-1c")}

    def prev_slide(self):
        self._store_slide()
        if self.index > 0:
            self.index -= 1
            self._load_slide()

    def next_slide(self):
        self._store_slide()
        if self.index < len(self.slides) - 1:
            self.index += 1
            self._load_slide()

    def add_slide(self):
        self._store_slide()
        self.slides.insert(self.index + 1, {"title": "New Slide", "body": ""})
        self.index += 1
        self._load_slide()

    def del_slide(self):
        if len(self.slides) <= 1:
            messagebox.showinfo("Slides", "You need at least one slide 🙂", parent=self)
            return
        self.slides.pop(self.index)
        self.index = max(0, self.index - 1)
        self._load_slide()

    # ------------------------------------------------------------ save/open
    def save_file(self):
        self._store_slide()
        name = self.current_file
        if not name:
            name = simpledialog.askstring("Save", "Name your slideshow:", parent=self)
            if not name:
                return
            if not name.endswith(".slides"):
                name += ".slides"
        d = kc.user_files_dir(self.session.get("username", "guest"))
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            json.dump(self.slides, fh)
        self.current_file = name
        messagebox.showinfo("Saved", f"Saved '{name}' 🎉", parent=self)

    def open_file(self):
        d = kc.user_files_dir(self.session.get("username", "guest"))
        decks = [n for n in sorted(os.listdir(d)) if n.endswith(".slides")]
        if not decks:
            messagebox.showinfo("Open", "No saved slideshows yet.", parent=self)
            return
        name = simpledialog.askstring("Open",
                                      "Type the name:\n" + "\n".join(decks),
                                      parent=self)
        if not name:
            return
        if not name.endswith(".slides"):
            name += ".slides"
        try:
            with open(os.path.join(d, name), encoding="utf-8") as fh:
                self.slides = json.load(fh)
            self.index = 0
            self.current_file = name
            self._load_slide()
        except Exception as e:
            messagebox.showerror("Open", f"Couldn't open that.\n{e}", parent=self)

    # ------------------------------------------------------------ together
    def _build_together(self, nb):
        f = tk.Frame(nb, bg=kc.PANEL)
        nb.add(f, text="  👫 Together  ")
        top = tk.Frame(f, bg=kc.PANEL)
        top.pack(fill="x", padx=10, pady=12)
        tk.Label(top, text="Room code:", bg=kc.PANEL, fg=kc.INK,
                 font=(kc.FONT, 15)).pack(side="left")
        self.room_entry = tk.Entry(top, font=(kc.FONT, 16, "bold"), width=10,
                                   bg="white", fg=kc.INK, relief="flat")
        self.room_entry.pack(side="left", padx=8, ipady=5)
        join = tk.Button(top, text="Join / Create", bg=kc.GREEN, fg="white",
                         command=self.join_room)
        kc.style_button(join)
        join.pack(side="left", padx=6)
        self.room_status = tk.Label(f, text="Share a code to build a slideshow "
                                            "with a friend!",
                                    bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 13))
        self.room_status.pack(anchor="w", padx=12)

    def join_room(self):
        code = self.room_entry.get().strip().upper()
        if not code:
            return
        self.room_code = code
        self.room_version = 0
        self.room_status.config(text=f"Connected to room {code}! Slides sync "
                                     "automatically. 🔄")
        self._schedule_room_sync()

    def _schedule_room_sync(self):
        if not self.room_code:
            return
        threading.Thread(target=self._room_tick, daemon=True).start()
        self.room_poll = self.after(3500, self._schedule_room_sync)

    def _room_tick(self):
        if not self.room_code:
            return
        self._store_slide()
        local = json.dumps(self.slides)
        status, data = kc.api(self.session, "POST", f"/api/room/{self.room_code}",
                              json_body={"content": local,
                                         "base_version": self.room_version,
                                         "kind": "ppt"})
        if status != 200 or not isinstance(data, dict):
            return
        if data.get("ok"):
            self.room_version = data.get("version", self.room_version)
        elif data.get("conflict"):
            try:
                incoming = json.loads(data.get("content", "[]"))
            except Exception:
                incoming = None
            self.room_version = data.get("version", self.room_version)
            if incoming:
                def adopt():
                    self.slides = incoming
                    self.index = min(self.index, len(self.slides) - 1)
                    self._load_slide()
                self.after(0, adopt)

    def destroy(self):
        if self.room_poll:
            try:
                self.after_cancel(self.room_poll)
            except Exception:
                pass
        super().destroy()


if __name__ == "__main__":
    KidSlides(kc.load_session()).mainloop()
