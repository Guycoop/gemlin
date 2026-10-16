"""The pet's windows on Windows and Linux, drawn with tkinter (it comes with Python).

All the decisions live in pet.py's Brain; this file only draws and listens to the mouse.
"""
import base64
import signal
import sys
import tkinter as tk
import webbrowser
from contextlib import suppress

from .paths import PACKAGE
from .pet import (HOP, INK, MUTED, PAD, PAPER, SCALE, SIZE, TAIL, TEXT_WIDTH, TICK, Brain, above_pet, beside_pet,
                 bubble_shape, png, review_spot)

CLEAR = "#ff00ff"  # the art never uses magenta, so it can be the see-through color
FONT, SMALL, CODE = ("Helvetica", 12), ("Helvetica", 9), ("Consolas", 10)
UI = "Segoe UI" if sys.platform == "win32" else "TkDefaultFont"  # the system's own font for the chat
ICONS = PACKAGE / "icons"

def system_theme():
    """Light or dark, plus the accent color, so the chat looks like the rest of Windows."""
    dark, accent = False, "#0067c0"
    if sys.platform == "win32":
        import winreg
        with suppress(OSError):
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                dark = winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        with suppress(OSError):
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
                abgr = winreg.QueryValueEx(key, "AccentColor")[0]  # stored as 0xAABBGGRR
                accent = "#%02x%02x%02x" % (abgr & 0xFF, abgr >> 8 & 0xFF, abgr >> 16 & 0xFF)
    if dark:
        return {"bg": "#2b2b2b", "fg": "#ffffff", "muted": "#a5a5a5", "field": "#1f1f1f", "line": "#454545", "accent": accent}
    return {"bg": "#f9f9f9", "fg": "#1b1b1b", "muted": "#5f5f5f", "field": "#ffffff", "line": "#d6d6d6", "accent": accent}

def see_through(win):
    """Make win borderless and always on top, with a background you can see through."""
    win.withdraw()
    win.overrideredirect(True)
    win.wm_attributes("-topmost", True)
    bg = PAPER  # Linux Tk can't do see-through windows, so the pet gets a small cream square
    with suppress(tk.TclError):
        win.wm_attributes("-transparentcolor", CLEAR)  # Windows
        bg = CLEAR
    win.configure(bg=bg)
    return bg

def floor_y(root):
    """The bottom of the usable screen: just above the taskbar."""
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes
        area = ctypes.wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(area), 0):  # SPI_GETWORKAREA
            return area.bottom
    return root.winfo_screenheight() - 40

class TkPet:
    def __init__(self, me, follow):
        self.root = root = tk.Tk()
        root.title(me["name"])
        self.bg = see_through(root)
        self.brain = Brain(me, root.winfo_screenwidth(), floor_y(root), follow)
        self.canvas = tk.Canvas(root, width=SIZE, height=SIZE + HOP, bg=self.bg, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.sprite = self.canvas.create_image(0, HOP, anchor="nw")
        self.images, self.shown, self.chat, self.review, self.bubble_size = {}, None, None, None, (0, 0)
        self.look_version, self.theme = 0, system_theme()
        self.bubble_win = tk.Toplevel(root)
        see_through(self.bubble_win)
        self.bubble = tk.Canvas(self.bubble_win, bg=self.bg, highlightthickness=0, bd=0)
        self.bubble.pack()
        self.bubble.bind("<Button-1>", lambda e: self.brain.bubble_clicked())
        self.menu, self.attention, self.tray = tk.Menu(root, tearoff=0), 0, None
        if sys.platform == "win32":
            with suppress(tk.TclError):
                root.iconbitmap(default=str(ICONS / "windows" / "Gemlin.ico"))  # Gemlin's icon on its windows
        self.canvas.bind("<ButtonPress-1>", lambda e: self.brain.pick_up(e.x_root, e.y_root))
        self.canvas.bind("<B1-Motion>", lambda e: self.brain.drag(e.x_root, e.y_root))
        self.canvas.bind("<ButtonRelease-1>", lambda e: self.brain.drop())
        for button in ("<Button-2>", "<Button-3>"):  # right-click
            self.canvas.bind(button, self.popup_menu)
        self.start_tray()
        self.step()
        root.deiconify()

    def popup_menu(self, event):  # built fresh each time, so checkmarks are current
        self.menu.delete(0, "end")
        for entry in self.brain.menu():
            if entry is None:
                self.menu.add_separator()
                continue
            title, action, checked = entry
            if checked is None:
                self.menu.add_command(label=title, command=lambda a=action: self.do(a))
            else:
                self.menu.add_checkbutton(label=title, command=lambda a=action: self.do(a),
                                          variable=tk.BooleanVar(self.root, value=checked))
        self.menu.tk_popup(event.x_root, event.y_root)

    def do(self, action):
        if page := self.brain.menu_action(action):
            webbrowser.open(page)

    def start_tray(self):
        """A Gemlin icon in the Windows system tray (or a Linux panel, if pystray is installed there).
        Left-click opens the chat; right-click has the same menu as Gemlin itself."""
        try:
            import pystray
            from PIL import Image
        except ImportError:
            return  # no tray: the right-click menu on Gemlin still has everything
        def entries():  # read fresh each time the tray menu opens
            for entry in self.brain.menu():
                if entry is None:
                    yield pystray.Menu.SEPARATOR
                    continue
                title, action, checked = entry
                tell = lambda icon, item, a=action: self.brain.events.put({"do": "menu", "action": a})  # noqa: E731
                yield pystray.MenuItem(title, tell, checked=None if checked is None else (lambda item, c=checked: c),
                                       default=action == "chat")
        image = Image.open(ICONS / ("windows/gemlin-32.png" if sys.platform == "win32" else "linux/tray/gemlin-dark-22.png"))
        with suppress(Exception):  # a desktop without a tray: carry on without it
            self.tray = pystray.Icon("gemlin", image, self.brain.me["name"], menu=pystray.Menu(entries))
            self.tray.run_detached()

    def step(self):
        b = self.brain
        b.step()
        if b.done:
            if self.tray:
                with suppress(Exception):
                    self.tray.stop()
            self.root.destroy()
            return
        if b.attention != self.attention:  # opened the Gemlin app, or picked Chat: come to the front
            self.attention = b.attention
            self.sync_chat()
            self.root.lift()
            if self.chat:
                self.chat.lift()
                self.chat.after(60, lambda: (self.chat.focus_force(), self.chat_entry.focus_force()))
        if b.look_version != self.look_version:  # new look: rebuild the sprites
            self.images, self.look_version = {}, b.look_version
        if b.frame not in self.images:
            data = base64.b64encode(png(b.art.frame(*b.frame))).decode()
            self.images[b.frame] = tk.PhotoImage(data=data, format="png").zoom(SCALE)
        self.canvas.itemconfigure(self.sprite, image=self.images[b.frame])
        self.canvas.coords(self.sprite, 0, HOP - b.lift)
        self.root.geometry(f"+{int(b.x)}+{int(b.y)}")
        self.sync_bubble(b.bubble)
        self.sync_chat()
        self.sync_review()
        self.root.after(TICK, self.step)

    def sync_bubble(self, want):
        if want != self.shown:
            self.shown = want
            if not want:
                self.bubble_win.withdraw()
                return
            text, footer = want
            c = self.bubble
            c.delete("all")
            words = c.create_text(PAD + 2, PAD - 2, text=text, width=TEXT_WIDTH, anchor="nw", fill=INK, font=FONT)
            x1, y1 = c.bbox(words)[2:]
            w, h = max(x1 + PAD, 70), y1 + PAD - 2
            if footer:
                c.create_text(w - PAD, h - 2, text=footer, anchor="ne", fill=MUTED, font=SMALL)
                h += 14
            c.tag_lower(c.create_polygon(bubble_shape(w, h), fill=PAPER, outline=INK, width=2))
            c.config(width=w, height=h + TAIL)
            self.bubble_size = (w, h + TAIL)
            self.bubble_win.deiconify()
        if want:
            self.bubble_win.geometry("+%d+%d" % above_pet(self.brain, *self.bubble_size))

    def panel(self):
        """A borderless window in the system's colors, for the chat box and the yes/no question."""
        t = self.theme
        win = tk.Toplevel(self.root, bg=t["bg"])
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        frame = tk.Frame(win, bg=t["bg"], highlightbackground=t["line"], highlightthickness=1, padx=14, pady=12)
        frame.pack()
        return win, frame

    def sync_chat(self):
        b, t = self.brain, self.theme
        mode = (b.needs_key, b.button, b.me["name"])
        if self.chat and (not b.chatting or mode != self.chat_mode):
            self.chat.destroy()
            self.chat = None
        if b.chatting and not self.chat:
            self.chat, frame = self.panel()
            self.chat_mode = mode
            tk.Label(frame, text="Paste your API key" if b.needs_key else f"Chat with {b.me['name']}",
                     bg=t["bg"], fg=t["fg"], font=(UI, 10, "bold")).pack(anchor="w")
            entry = tk.Entry(frame, width=34, font=(UI, 11), bg=t["field"], fg=t["fg"], relief="flat",
                             insertbackground=t["fg"], highlightthickness=1, highlightbackground=t["line"],
                             highlightcolor=t["accent"], show="•" if b.needs_key else "")
            entry.pack(pady=(6, 6), ipady=4, fill="x")
            row = tk.Frame(frame, bg=t["bg"])
            row.pack(fill="x")
            tk.Label(row, text="Enter to send · Esc to close", bg=t["bg"], fg=t["muted"], font=(UI, 8)).pack(side="left")
            tk.Button(row, text=b.button[0], font=(UI, 9), relief="flat", bg=t["accent"], fg="white",
                      activebackground=t["accent"], activeforeground="white", padx=8, cursor="hand2",
                      command=lambda: webbrowser.open(self.brain.button_clicked())).pack(side="right")
            entry.bind("<Return>", lambda e: (self.brain.heard(entry.get()), entry.delete(0, "end")))
            entry.bind("<Escape>", lambda e: setattr(self.brain, "chatting", False))
            edit = tk.Menu(entry, tearoff=0)  # right-click to paste (Ctrl+V works too)
            for label, event in (("Cut", "<<Cut>>"), ("Copy", "<<Copy>>"), ("Paste", "<<Paste>>"),
                                 ("Select all", "<<SelectAll>>")):
                edit.add_command(label=label, command=lambda ev=event: entry.event_generate(ev))
            for button in ("<Button-2>", "<Button-3>"):
                entry.bind(button, lambda e: edit.tk_popup(e.x_root, e.y_root))
            self.chat_entry = entry
            if not self.review:
                self.chat.after(60, lambda: (self.chat.focus_force(), entry.focus_force()))
        if self.chat:  # it follows the pet around, even while you drag it
            self.chat.geometry("+%d+%d" % beside_pet(b, self.chat.winfo_reqwidth(), self.chat.winfo_reqheight()))

    def sync_review(self):
        asking = self.brain.asking
        if self.review and (not asking or asking["id"] != self.review_id):
            self.review.destroy()
            self.review = None
            if self.chat:
                self.chat.after(60, lambda: (self.chat.focus_force(), self.chat_entry.focus_force()))
        if asking and not self.review:
            code = asking["code"]
            t = self.theme
            win, frame = self.panel()
            self.review, self.review_id = win, asking["id"]
            tk.Label(frame, text=asking["question"], bg=t["bg"], fg=t["fg"], font=(UI, 10), justify="left",
                     wraplength=520 if code else 300).pack(anchor="w")
            if code:
                box = tk.Frame(frame)
                box.pack(pady=(10, 0), fill="both")
                lines = code.count("\n") + 1
                text = tk.Text(box, width=72, height=min(22, lines), font=CODE, wrap="none", bg=t["field"], fg=t["fg"],
                               bd=0, highlightthickness=1, highlightbackground=t["line"])
                down = tk.Scrollbar(box, command=text.yview)
                across = tk.Scrollbar(box, orient="horizontal", command=text.xview)  # long lines stay readable
                text.configure(yscrollcommand=down.set, xscrollcommand=across.set)
                text.insert("1.0", code)
                text.configure(state="disabled")
                text.grid(row=0, column=0, sticky="nsew")
                down.grid(row=0, column=1, sticky="ns")
                across.grid(row=1, column=0, sticky="ew")
            buttons = tk.Frame(frame, bg=t["bg"])
            buttons.pack(anchor="e", pady=(12, 0))
            tk.Button(buttons, text="No", font=(UI, 10), width=8,
                      command=lambda: self.brain.answer(False)).pack(side="left", padx=(0, 8))
            tk.Button(buttons, text="Yes, install it" if code else "Yes", font=(UI, 10), bg=t["accent"], fg="white",
                      activebackground=t["accent"], activeforeground="white", relief="flat", padx=12,
                      command=lambda: self.brain.answer(True)).pack(side="left")
            win.bind("<Escape>", lambda e: self.brain.answer(False))  # Yes needs a click, so nothing gets approved by accident
            win.update_idletasks()
            win.geometry("+%d+%d" % review_spot(self.brain, win.winfo_reqwidth(), win.winfo_reqheight()))
            win.after(60, win.focus_force)

def run(me, follow):
    pet = TkPet(me, follow)
    # Ctrl+C: gemlin.py handles it (and we leave when it does); on our own, it puts the pet to sleep
    signal.signal(signal.SIGINT, signal.SIG_IGN if follow else lambda *a: setattr(pet.brain, "done", True))
    pet.root.mainloop()
