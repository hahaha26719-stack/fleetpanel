"""
FleetPanel Kid Slides (a fuller PowerPoint-style app for kids)
==============================================================
Features:
  * Slide list sidebar: add / duplicate / delete / move up/down, click to jump.
  * Per-slide: Title + Body text, with font SIZE, BOLD, ITALIC, text COLOR,
    alignment, and a slide BACKGROUND color.
  * Insert PICTURES from the policy-filtered picture search (via the Pi).
  * MATH: insert equations/symbols (√ × ÷ π ² ³ fractions, etc.) kid-friendly.
  * PRESENT mode: full-screen slideshow, arrow keys to move, Esc to exit.
  * Save / Open locally (roams to the Pi).
  * Together tab: collaborate on the deck using a room code (synced via Pi).

Standalone test:  python kidppt.py --windowed
"""
import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser

import kidcommon as kc

HERE = os.path.dirname(os.path.abspath(__file__))


def _new_slide(title="New Slide", body=""):
    """A slide with all the formatting fields (defaults keep old decks working)."""
    return {
        "title": title, "body": body,
        "font_size": 18, "bold": False, "italic": False,
        "color": "#2d2a32", "align": "left",
        "bg": "#ffffff",
        "pictures": [],   # list of {"title":.., "url":..}
        "math": [],       # list of math strings
    }


def _upgrade(slide):
    """Fill missing fields on an old {title, body} slide."""
    base = _new_slide()
    base.update(slide or {})
    return base


class KidSlides(tk.Tk):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.title("Slides")
        self.configure(bg=kc.BG)
        kc.maximize(self, windowed="--windowed" in sys.argv)
        self.slides = [_new_slide("My First Slide", "Type here!")]
        self.index = 0
        self.current_file = None
        self.room_code = None
        self.room_version = 0
        self.room_poll = None

        tk.Label(self, text="📊 My Slides", bg=kc.BG, fg=kc.INK,
                 font=(kc.FONT, 20, "bold")).pack(pady=(10, 4))
        nb = ttk.Notebook(self)
        nb.pack(expand=True, fill="both", padx=12, pady=8)
        self.nb = nb
        self._build_editor(nb)
        self._build_together(nb)
        self._refresh_slide_list()
        self._load_slide()

    # ----------------------------------------------------------- editor tab
    def _build_editor(self, nb):
        f = tk.Frame(nb, bg=kc.PANEL)
        nb.add(f, text="  📊 Slides  ")

        # --- top toolbar: slide ops + save/open + present ---
        bar = tk.Frame(f, bg=kc.PANEL)
        bar.pack(fill="x", padx=8, pady=6)
        for txt, col, cmd in [("➕ Add", kc.GREEN, self.add_slide),
                              ("⧉ Duplicate", kc.PRIMARY, self.dup_slide),
                              ("🗑 Delete", kc.RED, self.del_slide),
                              ("⬆", kc.PRIMARY, self.move_up),
                              ("⬇", kc.PRIMARY, self.move_down),
                              ("💾 Save", kc.YELLOW, self.save_file),
                              ("📂 Open", kc.PURPLE, self.open_file),
                              ("▶ Present", kc.GREEN, self.present)]:
            b = tk.Button(bar, text=txt, bg=col, fg="white", relief="flat", bd=0,
                          cursor="hand2", font=(kc.FONT, 12, "bold"), padx=10, pady=6,
                          command=cmd)
            b.pack(side="left", padx=3)

        # --- main area: left slide list, right editor ---
        main = tk.Frame(f, bg=kc.PANEL)
        main.pack(expand=True, fill="both", padx=8, pady=6)

        left = tk.Frame(main, bg=kc.PANEL, width=180)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="Slides", bg=kc.PANEL, fg=kc.MUT,
                 font=(kc.FONT, 12, "bold")).pack(anchor="w")
        self.slide_list = tk.Listbox(left, font=(kc.FONT, 12), bg="white", fg=kc.INK,
                                     relief="flat", selectbackground=kc.PRIMARY,
                                     activestyle="none")
        self.slide_list.pack(expand=True, fill="both", pady=4)
        self.slide_list.bind("<<ListboxSelect>>", self._pick_slide)

        right = tk.Frame(main, bg=kc.PANEL)
        right.pack(side="left", expand=True, fill="both", padx=(10, 0))

        # formatting toolbar
        fmt = tk.Frame(right, bg=kc.PANEL)
        fmt.pack(fill="x", pady=(0, 6))
        tk.Label(fmt, text="Size", bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 10)).pack(side="left")
        self.size_var = tk.IntVar(value=18)
        tk.Spinbox(fmt, from_=10, to=72, width=4, textvariable=self.size_var,
                   command=self._apply_format).pack(side="left", padx=(2, 10))
        self.bold_var = tk.BooleanVar()
        tk.Checkbutton(fmt, text="B", variable=self.bold_var, bg=kc.PANEL,
                       font=(kc.FONT, 11, "bold"), command=self._apply_format).pack(side="left")
        self.italic_var = tk.BooleanVar()
        tk.Checkbutton(fmt, text="I", variable=self.italic_var, bg=kc.PANEL,
                       font=(kc.FONT, 11, "italic"), command=self._apply_format).pack(side="left")
        tk.Button(fmt, text="🎨 Text", bg=kc.CARD if hasattr(kc,'CARD') else "#ddd",
                  fg=kc.INK, relief="flat", cursor="hand2", font=(kc.FONT, 10),
                  command=self.pick_text_color).pack(side="left", padx=6)
        tk.Button(fmt, text="🖌 Background", relief="flat", cursor="hand2",
                  font=(kc.FONT, 10), command=self.pick_bg_color).pack(side="left", padx=2)
        tk.Label(fmt, text="Align", bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 10)).pack(side="left", padx=(10, 2))
        self.align_var = tk.StringVar(value="left")
        for a, sym in [("left", "⬅"), ("center", "⬌"), ("right", "➡")]:
            tk.Radiobutton(fmt, text=sym, value=a, variable=self.align_var, bg=kc.PANEL,
                           font=(kc.FONT, 10), command=self._apply_format).pack(side="left")
        tk.Button(fmt, text="🖼 Picture", bg=kc.PINK, fg="white", relief="flat",
                  cursor="hand2", font=(kc.FONT, 10, "bold"), padx=8,
                  command=self.add_picture).pack(side="right", padx=2)
        tk.Button(fmt, text="∑ Math", bg=kc.PURPLE, fg="white", relief="flat",
                  cursor="hand2", font=(kc.FONT, 10, "bold"), padx=8,
                  command=self.add_math).pack(side="right", padx=2)

        tk.Label(right, text="Title", bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 11)).pack(anchor="w")
        self.title_entry = tk.Entry(right, font=(kc.FONT, 18, "bold"), bg="white",
                                    fg=kc.INK, relief="flat")
        self.title_entry.pack(fill="x", ipady=6, pady=(0, 8))
        self.title_entry.bind("<KeyRelease>", lambda e: self._store_slide())

        tk.Label(right, text="Text", bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 11)).pack(anchor="w")
        self.body_text = tk.Text(right, font=(kc.FONT, 16), wrap="word", bg="white",
                                fg=kc.INK, relief="flat", height=10, padx=8, pady=6)
        self.body_text.pack(expand=True, fill="both")
        self.body_text.bind("<KeyRelease>", lambda e: self._store_slide())

        self.extras = tk.Label(right, text="", bg=kc.PANEL, fg=kc.MUT,
                               font=(kc.FONT, 10), justify="left", anchor="w")
        self.extras.pack(fill="x", pady=(4, 0))

        # picture thumbnails shown under the editor
        self.pic_preview = tk.Frame(right, bg=kc.PANEL)
        self.pic_preview.pack(fill="x", pady=(4, 0))
        self._thumb_refs = []   # keep PhotoImage refs alive

        self.counter = tk.Label(right, text="", bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 11))
        self.counter.pack(anchor="e")

    # --------------------------------------------------------- slide model
    def _refresh_slide_list(self):
        self.slide_list.delete(0, "end")
        for i, s in enumerate(self.slides):
            self.slide_list.insert("end", f"{i+1}. {s.get('title','')[:18]}")
        self.slide_list.selection_clear(0, "end")
        self.slide_list.selection_set(self.index)

    def _pick_slide(self, _evt=None):
        sel = self.slide_list.curselection()
        if sel and sel[0] != self.index:
            self._store_slide()
            self.index = sel[0]
            self._load_slide()

    def _load_slide(self):
        s = _upgrade(self.slides[self.index])
        self.slides[self.index] = s
        self.title_entry.delete(0, "end"); self.title_entry.insert(0, s["title"])
        self.body_text.delete("1.0", "end"); self.body_text.insert("1.0", s["body"])
        # formatting controls
        self.size_var.set(s["font_size"]); self.bold_var.set(s["bold"])
        self.italic_var.set(s["italic"]); self.align_var.set(s["align"])
        self._apply_visual(s)
        self.counter.config(text=f"Slide {self.index+1} of {len(self.slides)}")
        extras = []
        if s["math"]:
            extras.append("∑ " + " ; ".join(s["math"]))
        self.extras.config(text="\n".join(extras))
        self._render_thumbs(s)
        self._refresh_slide_list()

    def _render_thumbs(self, s):
        """Show the ACTUAL picture thumbnails under the editor (needs Pillow)."""
        for w in self.pic_preview.winfo_children():
            w.destroy()
        self._thumb_refs = []
        if not s["pictures"]:
            return
        tk.Label(self.pic_preview, text="Pictures on this slide:", bg=kc.PANEL,
                 fg=kc.MUT, font=(kc.FONT, 10)).pack(anchor="w")
        row = tk.Frame(self.pic_preview, bg=kc.PANEL)
        row.pack(anchor="w")
        for p in s["pictures"]:
            cell = tk.Frame(row, bg=kc.PANEL)
            cell.pack(side="left", padx=6, pady=4)
            lbl = tk.Label(cell, text="🖼 " + (p.get("title", "pic")[:14]),
                           bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 9))
            lbl.pack()
            # fetch the real image in the background, then swap it in
            threading.Thread(target=self._load_thumb, args=(p, lbl), daemon=True).start()

    def _load_thumb(self, p, lbl):
        img = kc.fetch_image(self.session, p.get("url", ""), max_w=160, max_h=120)
        def swap():
            if img is not None:
                self._thumb_refs.append(img)
                try:
                    lbl.config(image=img, text="")
                except Exception:
                    pass
        self.after(0, swap)

    def _apply_visual(self, s):
        # reflect font/color/bg on the editor so it previews the slide
        font = (kc.FONT, s["font_size"],
                " ".join(x for x in [("bold" if s["bold"] else ""),
                                     ("italic" if s["italic"] else "")] if x) or "normal")
        self.body_text.config(font=font, fg=s["color"], bg=s["bg"])
        self.body_text.tag_configure("align", justify=s["align"])
        self.body_text.tag_add("align", "1.0", "end")
        self.title_entry.config(bg=s["bg"])

    def _store_slide(self):
        s = self.slides[self.index]
        s["title"] = self.title_entry.get()
        s["body"] = self.body_text.get("1.0", "end-1c")

    def _apply_format(self):
        s = self.slides[self.index]
        s["font_size"] = int(self.size_var.get())
        s["bold"] = bool(self.bold_var.get())
        s["italic"] = bool(self.italic_var.get())
        s["align"] = self.align_var.get()
        self._apply_visual(s)
        self._maybe_sync()

    def pick_text_color(self):
        c = colorchooser.askcolor(title="Text color", parent=self)
        if c and c[1]:
            self.slides[self.index]["color"] = c[1]
            self._apply_visual(self.slides[self.index]); self._maybe_sync()

    def pick_bg_color(self):
        c = colorchooser.askcolor(title="Slide background", parent=self)
        if c and c[1]:
            self.slides[self.index]["bg"] = c[1]
            self._apply_visual(self.slides[self.index]); self._maybe_sync()

    # ----------------------------------------------------- slide operations
    def add_slide(self):
        self._store_slide()
        self.slides.insert(self.index + 1, _new_slide())
        self.index += 1; self._load_slide(); self._maybe_sync()

    def dup_slide(self):
        self._store_slide()
        import copy
        self.slides.insert(self.index + 1, copy.deepcopy(self.slides[self.index]))
        self.index += 1; self._load_slide(); self._maybe_sync()

    def del_slide(self):
        if len(self.slides) <= 1:
            messagebox.showinfo("Slides", "You need at least one slide 🙂", parent=self); return
        self.slides.pop(self.index)
        self.index = max(0, self.index - 1); self._load_slide(); self._maybe_sync()

    def move_up(self):
        if self.index > 0:
            self._store_slide()
            self.slides[self.index-1], self.slides[self.index] = \
                self.slides[self.index], self.slides[self.index-1]
            self.index -= 1; self._load_slide(); self._maybe_sync()

    def move_down(self):
        if self.index < len(self.slides) - 1:
            self._store_slide()
            self.slides[self.index+1], self.slides[self.index] = \
                self.slides[self.index], self.slides[self.index+1]
            self.index += 1; self._load_slide(); self._maybe_sync()

    # ------------------------------------------------------------ pictures
    def add_picture(self):
        q = simpledialog.askstring("Add picture", "Search for a picture:", parent=self)
        if not q:
            return
        import urllib.parse
        self.extras.config(text="Searching for pictures… 🔎")
        def work():
            status, data = kc.api(self.session, "GET",
                                  f"/api/pictures/{self.session['username']}?q="
                                  + urllib.parse.quote(q))
            def done():
                if status != 200 or not isinstance(data, dict) or not data.get("results"):
                    msg = data.get("message", "No pictures found.") if isinstance(data, dict) else "Search failed."
                    self.extras.config(text=msg); return
                # let the kid pick one from the first few titles
                results = data["results"]
                choice = simpledialog.askstring(
                    "Pick a picture",
                    "Type the number:\n" + "\n".join(
                        f"{i+1}. {r.get('title','picture')[:40]}" for i, r in enumerate(results)),
                    parent=self)
                try:
                    idx = int(choice) - 1
                    pic = results[idx]
                except Exception:
                    return
                self.slides[self.index]["pictures"].append(
                    {"title": pic.get("title", ""), "url": pic.get("url", "")})
                self._load_slide(); self._maybe_sync()
            self.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- math
    def add_math(self):
        MathDialog(self, self._insert_math)

    def _insert_math(self, expr):
        if expr.strip():
            self.slides[self.index]["math"].append(expr.strip())
            # also drop it into the body so it's visible in the slide text
            self.body_text.insert("end", f"\n{expr.strip()}\n")
            self._store_slide(); self._load_slide(); self._maybe_sync()

    # ------------------------------------------------------------ present
    def present(self):
        self._store_slide()
        Present(self, self.slides, self.session)

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
            messagebox.showinfo("Open", "No saved slideshows yet.", parent=self); return
        name = simpledialog.askstring("Open", "Type the name:\n" + "\n".join(decks), parent=self)
        if not name:
            return
        if not name.endswith(".slides"):
            name += ".slides"
        try:
            with open(os.path.join(d, name), encoding="utf-8") as fh:
                self.slides = [_upgrade(s) for s in json.load(fh)]
            self.index = 0; self.current_file = name; self._load_slide()
        except Exception as e:
            messagebox.showerror("Open", f"Couldn't open that.\n{e}", parent=self)

    # ------------------------------------------------------------ together
    def _build_together(self, nb):
        f = tk.Frame(nb, bg=kc.PANEL)
        nb.add(f, text="  👫 Together  ")
        top = tk.Frame(f, bg=kc.PANEL); top.pack(fill="x", padx=10, pady=12)
        tk.Label(top, text="Room code:", bg=kc.PANEL, fg=kc.INK,
                 font=(kc.FONT, 15)).pack(side="left")
        self.room_entry = tk.Entry(top, font=(kc.FONT, 16, "bold"), width=10,
                                   bg="white", fg=kc.INK, relief="flat")
        self.room_entry.pack(side="left", padx=8, ipady=5)
        b = tk.Button(top, text="Join / Create", bg=kc.GREEN, fg="white", relief="flat",
                      cursor="hand2", font=(kc.FONT, 12, "bold"), padx=10, pady=6,
                      command=self.join_room)
        b.pack(side="left", padx=6)
        self.room_status = tk.Label(f, text="Share a code to build a slideshow with a friend!",
                                    bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 13))
        self.room_status.pack(anchor="w", padx=12)

    def join_room(self):
        code = self.room_entry.get().strip().upper()
        if not code:
            return
        self.room_code = code; self.room_version = 0
        self.room_status.config(text=f"Connected to room {code}! Slides sync automatically. 🔄")
        self._schedule_room_sync()

    def _maybe_sync(self):
        pass  # content is pushed on the room timer; nothing to do inline

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
                              json_body={"content": local, "base_version": self.room_version,
                                         "kind": "ppt"})
        if status != 200 or not isinstance(data, dict):
            return
        if data.get("ok"):
            self.room_version = data.get("version", self.room_version)
        elif data.get("conflict"):
            try:
                incoming = [_upgrade(s) for s in json.loads(data.get("content", "[]"))]
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


# -------------------------------------------------------------- math dialog
class MathDialog(tk.Toplevel):
    """Kid-friendly equation builder: buttons for common symbols, free typing."""
    SYMS = ["+", "−", "×", "÷", "=", "≠", "<", ">", "≤", "≥",
            "√", "π", "²", "³", "½", "¼", "¾", "°", "∞", "±",
            "(", ")", "∑", "∫", "Δ", "θ", "α", "β"]

    def __init__(self, parent, on_ok):
        super().__init__(parent)
        self.on_ok = on_ok
        self.title("Add Math")
        self.configure(bg=kc.PANEL)
        self.geometry("460x300")
        tk.Label(self, text="Build an equation", bg=kc.PANEL, fg=kc.INK,
                 font=(kc.FONT, 15, "bold")).pack(pady=8)
        self.entry = tk.Entry(self, font=(kc.FONT, 18), bg="white", fg=kc.INK, relief="flat")
        self.entry.pack(fill="x", padx=12, ipady=8)
        grid = tk.Frame(self, bg=kc.PANEL); grid.pack(pady=8)
        for i, sym in enumerate(self.SYMS):
            tk.Button(grid, text=sym, width=3, font=(kc.FONT, 13), relief="flat",
                      bg="white", cursor="hand2",
                      command=lambda s=sym: self.entry.insert("insert", s)
                      ).grid(row=i // 10, column=i % 10, padx=2, pady=2)
        tk.Label(self, text="Tip: type numbers and letters too. Use / for fractions.",
                 bg=kc.PANEL, fg=kc.MUT, font=(kc.FONT, 10)).pack(pady=(4, 0))
        bar = tk.Frame(self, bg=kc.PANEL); bar.pack(pady=10)
        tk.Button(bar, text="Add to slide", bg=kc.GREEN, fg="white", relief="flat",
                  cursor="hand2", font=(kc.FONT, 12, "bold"), padx=14, pady=6,
                  command=self._ok).pack(side="left", padx=6)
        tk.Button(bar, text="Cancel", bg=kc.MUT, fg="white", relief="flat",
                  cursor="hand2", font=(kc.FONT, 12), padx=14, pady=6,
                  command=self.destroy).pack(side="left")
        self.entry.focus_set()

    def _ok(self):
        self.on_ok(self.entry.get())
        self.destroy()


# ------------------------------------------------------------- present mode
class Present(tk.Toplevel):
    """Full-screen slideshow. Arrow keys / click to move, Esc to exit."""
    def __init__(self, parent, slides, session):
        super().__init__(parent)
        self.slides = slides
        self.parent_session = session
        self._present_refs = []
        self.i = 0
        self.attributes("-fullscreen", True)
        self.configure(bg="black")
        self.canvas = tk.Frame(self, bg="white")
        self.canvas.pack(expand=True, fill="both")
        self.bind("<Right>", lambda e: self.go(1))
        self.bind("<Left>", lambda e: self.go(-1))
        self.bind("<space>", lambda e: self.go(1))
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Button-1>", lambda e: self.go(1))
        self.focus_force()
        self._render()

    def go(self, d):
        self.i = max(0, min(len(self.slides) - 1, self.i + d))
        self._render()

    def _render(self):
        for w in self.canvas.winfo_children():
            w.destroy()
        s = _upgrade(self.slides[self.i])
        self.canvas.config(bg=s["bg"])
        font = (kc.FONT, max(s["font_size"], 20),
                " ".join(x for x in [("bold" if s["bold"] else ""),
                                     ("italic" if s["italic"] else "")] if x) or "normal")
        tk.Label(self.canvas, text=s["title"], bg=s["bg"], fg=s["color"],
                 font=(kc.FONT, max(s["font_size"] + 16, 40), "bold")).pack(pady=(60, 20))
        tk.Label(self.canvas, text=s["body"], bg=s["bg"], fg=s["color"], font=font,
                 wraplength=self.winfo_screenwidth() - 160, justify=s["align"]).pack(padx=80)
        for m in s.get("math", []):
            tk.Label(self.canvas, text=m, bg=s["bg"], fg=s["color"],
                     font=(kc.FONT, max(s["font_size"] + 6, 28))).pack(pady=4)
        # show ACTUAL pictures (fetched via the Pi, needs Pillow)
        self._present_refs = []
        for p in s.get("pictures", []):
            holder = tk.Label(self.canvas, text="🖼 " + p.get("title", ""), bg=s["bg"],
                              fg=s["color"], font=(kc.FONT, 14))
            holder.pack(pady=6)
            threading.Thread(target=self._present_img, args=(p, holder, s["bg"]),
                             daemon=True).start()

    def _present_img(self, p, holder, bg):
        img = kc.fetch_image(self.parent_session, p.get("url", ""), max_w=640, max_h=420)
        def swap():
            if img is not None:
                self._present_refs.append(img)
                try:
                    holder.config(image=img, text="", bg=bg)
                except Exception:
                    pass
        self.after(0, swap)
        tk.Label(self.canvas, text=f"{self.i+1} / {len(self.slides)}   (→ next, Esc exit)",
                 bg=s["bg"], fg="#999", font=(kc.FONT, 11)).pack(side="bottom", pady=10)


if __name__ == "__main__":
    KidSlides(kc.load_session()).mainloop()
