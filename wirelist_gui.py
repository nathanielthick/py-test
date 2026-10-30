#!/usr/bin/env python3
"""
wirelist_gui.py

Desktop GUI for wirelist_to_instructions.py (Impact ES / Cirris).

Place this file in the same folder as wirelist_to_instructions.py and run:
    python wirelist_gui.py

The wire list and label list can be pasted straight into their boxes or
loaded with "Open file…" (loaded text can still be edited before converting).

Logos
-----
The header shows the Impact ES logo on the left and the Cirris logo on the
right. Put the image files next to this script (or in an "assets" subfolder).
Any PNG/GIF whose file name contains "impact" or "cirris" is picked up, e.g.
    impact_es_logo.png
    cirris_logo.png
If Pillow is installed (pip install pillow) JPG files also work and logos are
scaled smoothly; without it, PNG/GIF are scaled down by whole-number steps.
If a logo is missing, a text placeholder is shown instead.
"""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

if getattr(sys, "frozen", False):
    # Running as a PyInstaller .exe: user files live next to the .exe,
    # bundled files (e.g. logos added with --add-data) in sys._MEIPASS.
    HERE = os.path.dirname(sys.executable)
    BUNDLE = getattr(sys, "_MEIPASS", HERE)
else:
    HERE = BUNDLE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    import wirelist_to_instructions as core
except ImportError:
    tk.Tk().withdraw()
    messagebox.showerror(
        "Missing script",
        "wirelist_to_instructions.py was not found.\n\n"
        "Put wirelist_gui.py in the same folder as wirelist_to_instructions.py.")
    sys.exit(1)

try:
    from PIL import Image, ImageTk  # optional
except ImportError:
    Image = ImageTk = None

APP_TITLE = "Wire List → Cirris Instructions"
LOGO_HEIGHT = 56

# Colours
BG = "#f4f6f9"
HEADER_BG = "#ffffff"
ACCENT = "#0b4f8a"
ACCENT_HOVER = "#093f6e"
TEXT = "#1d2733"
MUTED = "#5b6775"
ERR = "#b42318"
WARN = "#b54708"
OK = "#067647"


# --------------------------------------------------------------------------- #
# Logo helpers
# --------------------------------------------------------------------------- #
def find_logo(keyword):
    exts = (".png", ".gif") + ((".jpg", ".jpeg") if Image else ())
    folders = []
    for base in dict.fromkeys((HERE, BUNDLE)):  # logos next to the .exe win
        folders += [base, os.path.join(base, "assets"), os.path.join(base, "images")]
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            low = name.lower()
            if keyword in low and low.endswith(exts):
                return os.path.join(folder, name)
    return None


def load_logo(path, height):
    try:
        if Image:
            img = Image.open(path).convert("RGBA")
            w = max(1, int(img.width * height / img.height))
            return ImageTk.PhotoImage(img.resize((w, height), Image.LANCZOS))
        img = tk.PhotoImage(file=path)
        factor = max(1, round(img.height() / height))
        return img.subsample(factor, factor) if factor > 1 else img
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Conversion (reuses the command-line script's functions)
# --------------------------------------------------------------------------- #
def normalise_labels(text):
    """Accept a full CUSTOM_LABELS block or just the 'J1-1, _J1-1' lines."""
    if "CUSTOM_LABELS" in text.upper():
        return text
    body = "\n".join("     " + ln.strip() for ln in text.splitlines()
                     if ln.strip() and ln.strip().upper() not in ("BEGIN", "END"))
    return f"CUSTOM_LABELS\nBEGIN\n{body}\nEND\n"


def convert(wire_text, label_text, ohms):
    """Return (instruction text or None, wire count, error count, messages).

    The command-line script reads from files, so the text from the boxes is
    written to temporary files and handed to its functions unchanged.
    """
    tmpdir = tempfile.mkdtemp(prefix="wirelist_")
    wire_path = os.path.join(tmpdir, "wires.csv")
    label_path = os.path.join(tmpdir, "labels.txt")
    try:
        with open(wire_path, "w", encoding="utf-8") as f:
            f.write(wire_text)
        with open(label_path, "w", encoding="utf-8") as f:
            f.write(normalise_labels(label_text))

        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            try:
                label_to_point, points = core.parse_labels(label_path)
            except SystemExit as e:
                msg = str(e.code) if e.code not in (None, 0, 1) else ""
                return None, 0, 1, (log.getvalue() + msg).strip()
            wires, errors = core.build_instructions(wire_path, label_to_point,
                                                    points, ohms)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    text = ("INSTRUCTIONS\nBEGIN\n" + "\n".join(wires)
            + ("\n" if wires else "") + "END\n")
    # Temp file names mean nothing to the user - talk about the boxes instead.
    log_text = (log.getvalue().replace("wire list line", "Wire list line")
                .replace("label file line", "Label list line").strip())
    return text, len(wires), errors, log_text


def read_text(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
class InputPane(ttk.LabelFrame):
    """A titled, editable text box with Open / Paste / Clear buttons."""

    def __init__(self, master, app, title, hint, filetypes):
        super().__init__(master, text=f"  {title}  ", style="Card.TLabelframe",
                         padding=(10, 6, 10, 10))
        self.app, self.title, self.filetypes = app, title, filetypes
        self.source = tk.StringVar(value=hint)

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Open file…", command=self.open).pack(side="left")
        ttk.Button(bar, text="Paste", command=self.paste).pack(side="left", padx=6)
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left")
        self.count = ttk.Label(bar, style="Muted.TLabel")
        self.count.pack(side="right")

        self.text = make_text(self, editable=True)
        self.text.master.pack(fill="both", expand=True)
        self.text.bind("<<Modified>>", self._modified)

        ttk.Label(self, textvariable=self.source, style="Muted.TLabel",
                  anchor="w").pack(fill="x", pady=(6, 0))

    def get(self):
        return self.text.get("1.0", "end-1c")

    def set(self, content, source):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.edit_modified(True)
        self.source.set(source)

    def open(self):
        path = filedialog.askopenfilename(title=f"Open {self.title.lower()}",
                                          initialdir=self.app.last_dir,
                                          filetypes=self.filetypes)
        if path:
            self.load(path)

    def load(self, path):
        try:
            self.set(read_text(path), f"Loaded from {path}")
            self.app.last_dir = os.path.dirname(path)
        except OSError as e:
            messagebox.showerror(APP_TITLE, f"Could not open {path}:\n\n{e}")

    def paste(self):
        try:
            clip = self.app.clipboard_get()
        except tk.TclError:
            self.app._status("The clipboard is empty.", WARN)
            return
        self.set(clip, "Pasted from clipboard")

    def clear(self):
        self.set("", "Empty - paste text or open a file")

    def _modified(self, _event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        n = sum(1 for ln in self.get().splitlines() if ln.strip())
        self.count.configure(text=f"{n} line(s)")


def make_text(parent, editable=False):
    holder = ttk.Frame(parent)
    txt = tk.Text(holder, wrap="none", height=8, width=30, font=("Consolas", 10),
                  bg="white", fg=TEXT, relief="flat", padx=8, pady=6,
                  borderwidth=0, highlightthickness=1,
                  highlightbackground="#d0d7e2", highlightcolor=ACCENT,
                  undo=editable, insertbackground=TEXT)
    ys = ttk.Scrollbar(holder, orient="vertical", command=txt.yview)
    xs = ttk.Scrollbar(holder, orient="horizontal", command=txt.xview)
    txt.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
    if not editable:
        txt.configure(state="disabled")
    txt.grid(row=0, column=0, sticky="nsew")
    ys.grid(row=0, column=1, sticky="ns")
    xs.grid(row=1, column=0, sticky="ew")
    holder.rowconfigure(0, weight=1)
    holder.columnconfigure(0, weight=1)
    return txt


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x760")
        self.minsize(900, 560)
        self.configure(bg=BG)

        self.out_var = tk.StringVar()
        self.ohm_var = tk.StringVar(value="10.0")
        self.status_var = tk.StringVar(
            value="Paste or open a wire list and a label list, then click Convert.")
        self.last_dir = HERE
        self.result = None
        self._logos = []  # keep references so Tk doesn't discard images

        self._style()
        self._header()
        self._statusbar()   # packed early so it is never squeezed out
        self._options_row()
        self._body()
        self._prefill()

        self.bind("<Control-Return>", lambda e: self.run())
        self.bind("<Control-s>", lambda e: self.save())

    # ---- styling ---------------------------------------------------------- #
    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        s.configure("Card.TLabelframe", background=BG, bordercolor="#d0d7e2")
        s.configure("Card.TLabelframe.Label", background=BG, foreground=ACCENT,
                    font=("Segoe UI Semibold", 10))
        s.configure("TLabel", background=BG)
        s.configure("Muted.TLabel", background=BG, foreground=MUTED)
        s.configure("TEntry", fieldbackground="white", padding=4)
        s.configure("TButton", padding=(10, 4))
        s.configure("Accent.TButton", background=ACCENT, foreground="white",
                    font=("Segoe UI Semibold", 11), padding=(22, 7), borderwidth=0)
        s.map("Accent.TButton", background=[("active", ACCENT_HOVER),
                                            ("disabled", "#9aa8b8")])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(12, 5))

    # ---- header with logos ------------------------------------------------ #
    def _header(self):
        bar = tk.Frame(self, bg=HEADER_BG, height=LOGO_HEIGHT + 24)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Frame(self, bg=ACCENT, height=3).pack(fill="x")

        self._logo_slot(bar, "impact", "IMPACT ES").pack(side="left", padx=16)
        self._logo_slot(bar, "cirris", "CIRRIS").pack(side="right", padx=16)

        mid = tk.Frame(bar, bg=HEADER_BG)
        mid.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(mid, text="Wire List Converter", bg=HEADER_BG, fg=TEXT,
                 font=("Segoe UI Semibold", 16)).pack()
        tk.Label(mid, text="Wire list + CUSTOM_LABELS  →  Cirris WIRE instructions",
                 bg=HEADER_BG, fg=MUTED, font=("Segoe UI", 9)).pack()

    def _logo_slot(self, parent, keyword, fallback):
        path = find_logo(keyword)
        img = load_logo(path, LOGO_HEIGHT) if path else None
        if img:
            self._logos.append(img)
            return tk.Label(parent, image=img, bg=HEADER_BG)
        return tk.Label(parent, text=fallback, bg=HEADER_BG, fg=ACCENT,
                        font=("Segoe UI Black", 15))

    # ---- options row ------------------------------------------------------ #
    def _options_row(self):
        row = ttk.Frame(self, padding=(16, 12, 16, 4))
        row.pack(fill="x")

        ttk.Label(row, text="Resistance per wire").pack(side="left")
        ttk.Spinbox(row, from_=0.1, to=1000, increment=0.5, width=7,
                    textvariable=self.ohm_var).pack(side="left", padx=(8, 3))
        ttk.Label(row, text="Ω", style="Muted.TLabel").pack(side="left")

        ttk.Label(row, text="Also save to").pack(side="left", padx=(24, 8))
        ttk.Entry(row, textvariable=self.out_var).pack(side="left", fill="x",
                                                       expand=True)
        ttk.Button(row, text="Browse…", command=self._pick_save).pack(side="left",
                                                                     padx=(6, 0))

        self.run_btn = ttk.Button(row, text="Convert  ▶", style="Accent.TButton",
                                  command=self.run)
        self.run_btn.pack(side="right", padx=(16, 0))

    def _pick_save(self):
        path = filedialog.asksaveasfilename(title="Save instructions as",
                                            initialdir=self.last_dir,
                                            defaultextension=".txt",
                                            filetypes=[("Text", "*.txt"),
                                                       ("All files", "*.*")])
        if path:
            self.out_var.set(path)
        return path

    # ---- three columns: wire list | label list | output ------------------- #
    def _body(self):
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=16, pady=(8, 10))

        self.wires = InputPane(
            panes, self, "Wire list",
            "Paste lines like  _J1-52,P1-1  or open a .csv file",
            [("CSV / text", "*.csv *.txt"), ("All files", "*.*")])
        self.labels = InputPane(
            panes, self, "Label list",
            "Paste a CUSTOM_LABELS block (or just  J1-1, _J1-1  lines) or open a file",
            [("Text", "*.txt *.lbl"), ("All files", "*.*")])

        out = ttk.LabelFrame(panes, text="  Output  ", style="Card.TLabelframe",
                             padding=(10, 6, 10, 10))
        self.tabs = ttk.Notebook(out)
        self.tabs.pack(fill="both", expand=True)
        self.preview = make_text(self.tabs)
        self.messages = make_text(self.tabs)
        self.messages.configure(wrap="word")
        self.tabs.add(self.preview.master, text=" Instructions ")
        self.tabs.add(self.messages.master, text=" Messages ")
        for tag, colour in (("err", ERR), ("warn", WARN), ("ok", OK)):
            self.messages.tag_configure(tag, foreground=colour)

        btns = ttk.Frame(out)
        btns.pack(fill="x", pady=(8, 0))
        self.save_btn = ttk.Button(btns, text="Save as…", command=self.save_as,
                                   state="disabled")
        self.save_btn.pack(side="right")
        self.copy_btn = ttk.Button(btns, text="Copy", command=self.copy,
                                   state="disabled")
        self.copy_btn.pack(side="right", padx=6)

        panes.add(self.wires, weight=1)
        panes.add(self.labels, weight=1)
        panes.add(out, weight=1)

    def _prefill(self):
        """Load wires.csv / labels.txt from the program's folder if present."""
        for pane, name in ((self.wires, "wires.csv"), (self.labels, "labels.txt")):
            p = os.path.join(HERE, name)
            if os.path.isfile(p):
                pane.load(p)

    # ---- status bar ------------------------------------------------------- #
    def _statusbar(self):
        bar = tk.Frame(self, bg="#e6ebf1")
        bar.pack(fill="x", side="bottom")
        self.status_lbl = tk.Label(bar, textvariable=self.status_var, bg="#e6ebf1",
                                   fg=MUTED, anchor="w", padx=16, pady=5,
                                   font=("Segoe UI", 9))
        self.status_lbl.pack(fill="x")

    def _status(self, text, colour=MUTED):
        self.status_var.set(text)
        self.status_lbl.configure(fg=colour)

    def _set_text(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    # ---- actions ---------------------------------------------------------- #
    def run(self):
        wire_text, label_text = self.wires.get(), self.labels.get()
        for text, what in ((wire_text, "wire list"), (label_text, "label list")):
            if not text.strip():
                messagebox.showwarning(APP_TITLE,
                                       f"The {what} is empty.\n\n"
                                       "Paste it into the box or use Open file….")
                return
        try:
            ohms = float(self.ohm_var.get())
        except ValueError:
            messagebox.showwarning(APP_TITLE, "Resistance must be a number.")
            return

        try:
            text, count, errors, log = convert(wire_text, label_text, ohms)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Conversion failed:\n\n{e}")
            return

        self.result = text
        self._set_text(self.preview, text or "")
        self._show_messages(log, count, errors, text is not None)
        state = "normal" if text else "disabled"
        self.save_btn.configure(state=state)
        self.copy_btn.configure(state=state)

        if text is None:
            self._status("The label list could not be read - see Messages.", ERR)
            self.tabs.select(1)
            return

        out = self.out_var.get().strip()
        saved = self._write(out) if out else False
        msg = f"{count} wire(s) converted"
        if saved:
            msg += f" and saved to {os.path.basename(out)}"
        if errors:
            self._status(msg + f"  •  {errors} line(s) had problems - see Messages",
                         WARN)
        else:
            self._status(msg + ".", OK)
        self.tabs.select(1 if errors else 0)

    def _show_messages(self, log, count, errors, ok):
        self.messages.configure(state="normal")
        self.messages.delete("1.0", "end")
        for line in filter(None, log.splitlines()):
            tag = "err" if line.lower().startswith("error") else "warn"
            self.messages.insert("end", line + "\n", tag)
        if ok:
            tag = "warn" if errors else "ok"
            self.messages.insert("end", f"\n{count} wire(s) written, "
                                        f"{errors} line(s) with problems.\n", tag)
        self.messages.configure(state="disabled")

    def _write(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.result)
            return True
        except OSError as e:
            messagebox.showerror(APP_TITLE, f"Could not save {path}:\n\n{e}")
            return False

    def save(self):
        if not self.result:
            return
        out = self.out_var.get().strip()
        if not out:
            return self.save_as()
        if self._write(out):
            self._status(f"Saved to {out}", OK)

    def save_as(self):
        if not self.result:
            return
        if self._pick_save():
            self.save()

    def copy(self):
        if self.result:
            self.clipboard_clear()
            self.clipboard_append(self.result)
            self._status("Instructions copied to clipboard - paste into "
                         "your Cirris file.", OK)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:  # sharp text on high-DPI displays
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()
