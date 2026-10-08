"""
FleetPanel Kid Notepad
======================
A simple, child-friendly notepad with four tabs:
  1. Write     - a big friendly text editor
  2. My Files  - save/open notes locally (also roam to the Pi via login_app)
  3. Pictures  - picture search via the Pi (Openverse), filtered by picture_mode
                 policy; works even when the web browser is blocked
  4. Together  - collaborate with others using a room code (synced via the Pi)

Standalone test:  python kidnotepad.py --windowed
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import kidcommon as kc

HERE = os.path.dirname(os.path.abspath(__file__))


class KidNotepad(tk.Tk):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.title("Notepad")
        self.configure(bg=kc.BG)
        kc.maximize(self, windowed="--windowed" in sys.argv)
        self.current_file = None

        # collaboration state
        self.room_code = None
        self.room_version = 0
        self.room_poll = None

        header = tk.Label(self, text="📝 My Notepad", bg=kc.BG, fg=kc.INK,
                          font=(kc.FONT, 22, "bold"))
        header.pack(pady=(14, 6))

        nb = ttk.Notebook(self)
        nb.pack(expand=True, fill="both", padx=14, pady=10)
        self.nb = nb
        self._build_write(nb)
        self._build_files(nb)
        self._build_pictures(nb)
        self._build_together(nb)

    # ------------------------------------------------------------- 1. Write
    def _build_write(self, nb):
        f = tk.Frame(nb, bg=kc.PANEL)
        nb.add(f, text="  ✏️ Write  ")
        self.text = tk.Text(f, font=(kc.FONT, 16), wrap="word", bg="white",
                            fg=kc.INK, insertbackground=kc.INK, relief="flat",
                            padx=14, pady=12, undo=True)
        self.text.pack(expand=True, fill="both", padx=10, pady=10)

    # --------------------------------------------------------- 2. My Files
    def _build_files(self, nb):
        f = tk.Frame(nb, bg=kc.PANEL)
        nb.add(f, text="  📁 My Files  ")
        bar = tk.Frame(f, bg=kc.PANEL)
        bar.pack(fill="x", padx=10, pady=10)
        for txt, col, cmd in [("💾 Save", kc.GREEN, self.save_file),
                              ("📂 Open", kc.PRIMARY, self.open_selected),
                              ("🔄 Refresh", kc.YELLOW, self.refresh_files)]:
            b = tk.Button(bar, text=txt, bg=col, fg="white", command=cmd)
            kc.style_button(b)
            b.pack(side="left", padx=6)
        self.filelist = tk.Listbox(f, font=(kc.FONT, 15), bg="white", fg=kc.INK,
                                   relief="flat", selectbackground=kc.PRIMARY)
        self.filelist.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        self.refresh_files()

    def refresh_files(self):
        self.filelist.delete(0, "end")
        d = kc.user_files_dir(self.session.get("username", "guest"))
        for name in sorted(os.listdir(d)):
            if name.endswith(".txt"):
                self.filelist.insert("end", name)

    def save_file(self):
        name = self.current_file
        if not name:
            name = simpledialog.askstring("Save", "Name your note:", parent=self)
            if not name:
                return
            if not name.endswith(".txt"):
                name += ".txt"
        d = kc.user_files_dir(self.session.get("username", "guest"))
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write(self.text.get("1.0", "end-1c"))
        self.current_file = name
        self.refresh_files()
        messagebox.showinfo("Saved", f"Saved '{name}' 🎉", parent=self)

    def open_selected(self):
        sel = self.filelist.curselection()
        if not sel:
            messagebox.showinfo("Open", "Pick a file from the list first.", parent=self)
            return
        name = self.filelist.get(sel[0])
        d = kc.user_files_dir(self.session.get("username", "guest"))
        with open(os.path.join(d, name), encoding="utf-8") as fh:
            self.text.delete("1.0", "end")
            self.text.insert("1.0", fh.read())
        self.current_file = name
        self.nb.select(0)  # jump to Write tab

    # --------------------------------------------------------- 3. Pictures
    def _build_pictures(self, nb):
        f = tk.Frame(nb, bg=kc.PANEL)
        nb.add(f, text="  🖼️ Pictures  ")
        bar = tk.Frame(f, bg=kc.PANEL)
        bar.pack(fill="x", padx=10, pady=10)
        self.pic_entry = tk.Entry(bar, font=(kc.FONT, 16), bg="white", fg=kc.INK,
                                  relief="flat")
        self.pic_entry.pack(side="left", expand=True, fill="x", ipady=6, padx=(0, 8))
        self.pic_entry.bind("<Return>", lambda e: self.search_pictures())
        go = tk.Button(bar, text="🔍 Search", bg=kc.PRIMARY, fg="white",
                       command=self.search_pictures)
        kc.style_button(go)
        go.pack(side="left")
        self.pic_msg = tk.Label(f, text="Search for pictures to add to your notes!",
                                bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 13))
        self.pic_msg.pack(anchor="w", padx=12)
        self.pic_area = tk.Frame(f, bg=kc.PANEL)
        self.pic_area.pack(expand=True, fill="both", padx=10, pady=10)

    def search_pictures(self):
        q = self.pic_entry.get().strip()
        if not q:
            return
        self.pic_msg.config(text="Looking… 🔎")
        for w in self.pic_area.winfo_children():
            w.destroy()
        threading.Thread(target=self._do_search, args=(q,), daemon=True).start()

    def _do_search(self, q):
        import urllib.parse
        status, data = kc.api(self.session, "GET",
                              f"/api/pictures/{self.session['username']}?q="
                              + urllib.parse.quote(q))
        def show():
            if status != 200 or not isinstance(data, dict):
                self.pic_msg.config(text="Couldn't search right now. Try again. 🙂")
                return
            results = data.get("results", [])
            if not results:
                self.pic_msg.config(text=data.get("message", "No pictures found."))
                return
            self.pic_msg.config(text=f"Found {len(results)} pictures! "
                                     "Click one to copy its name into your note.")
            # show titles as clickable chips (thumbnails need Pillow; keep it
            # dependency-free by listing titles the kid can insert)
            for item in results:
                t = item.get("title") or "picture"
                b = tk.Button(self.pic_area, text="🖼️ " + t[:40], bg="white",
                              fg=kc.INK, relief="flat", anchor="w",
                              font=(kc.FONT, 12), cursor="hand2",
                              command=lambda it=item: self._insert_picture(it))
                b.pack(fill="x", padx=4, pady=2)
        self.after(0, show)

    def _insert_picture(self, item):
        # Insert the ACTUAL image into the note (needs Pillow). Falls back to a
        # text reference if Pillow isn't installed or the fetch fails.
        self.nb.select(0)
        if not hasattr(self, "_img_refs"):
            self._img_refs = []
        self.text.insert("end", f"\n[{item.get('title','picture')}]\n")

        def work():
            img = kc.fetch_image(self.session, item.get("url", ""), max_w=360, max_h=260)
            def place():
                if img is not None:
                    self._img_refs.append(img)   # keep a reference alive
                    self.text.image_create("end", image=img)
                    self.text.insert("end", "\n")
                else:
                    self.text.insert("end", f"(picture: {item.get('url','')})\n")
            self.after(0, place)
        threading.Thread(target=work, daemon=True).start()

    # --------------------------------------------------------- 4. Together
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
        self.room_status = tk.Label(f, text="Enter a code and share it with a friend "
                                            "to write together!",
                                    bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 13))
        self.room_status.pack(anchor="w", padx=12)
        tk.Label(f, text="(Shares the text from the Write tab.)",
                 bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 11)).pack(anchor="w", padx=12)

    def join_room(self):
        code = self.room_entry.get().strip().upper()
        if not code:
            return
        self.room_code = code
        self.room_version = 0
        self.room_status.config(text=f"Connected to room {code}! Changes sync "
                                     "automatically. 🔄")
        self._schedule_room_sync()

    def _schedule_room_sync(self):
        if not self.room_code:
            return
        threading.Thread(target=self._room_tick, daemon=True).start()
        # poll every 3s (light on the Pi)
        self.room_poll = self.after(3000, self._schedule_room_sync)

    def _room_tick(self):
        if not self.room_code:
            return
        local = self.text.get("1.0", "end-1c")
        # push our content; if the server has a newer version, pull it instead
        status, data = kc.api(self.session, "POST", f"/api/room/{self.room_code}",
                              json_body={"content": local,
                                         "base_version": self.room_version,
                                         "kind": "note"})
        if status != 200 or not isinstance(data, dict):
            return
        if data.get("ok"):
            self.room_version = data.get("version", self.room_version)
        elif data.get("conflict"):
            # someone else is newer -> adopt theirs
            newtext = data.get("content", "")
            self.room_version = data.get("version", self.room_version)
            def adopt():
                if self.text.get("1.0", "end-1c") != newtext:
                    cur = self.text.index("insert")
                    self.text.delete("1.0", "end")
                    self.text.insert("1.0", newtext)
                    try:
                        self.text.mark_set("insert", cur)
                    except Exception:
                        pass
            self.after(0, adopt)

    def destroy(self):
        if self.room_poll:
            try:
                self.after_cancel(self.room_poll)
            except Exception:
                pass
        super().destroy()


if __name__ == "__main__":
    KidNotepad(kc.load_session()).mainloop()
