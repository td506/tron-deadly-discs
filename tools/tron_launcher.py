"""The TRON Deadly Discs launcher window: pick mods, display and controller,
check the files it needs, then Play.  Choices are saved to tron_settings.ini;
tron_build.py does the building and starts jzIntv."""
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

import right_stick
import tron_build as tb

MOD_GROUPS = [  # (heading, MOD_* symbols)
    ("Look", ["MOD_COLORS", "MOD_RECOG_NO_SHIELD", "MOD_RECOG_BIG_EYE", "MOD_DEREZZED"]),
    ("Scoring", ["MOD_START_SCORE", "MOD_POINT_TIER", "MOD_TOP_TIER", "MOD_CROSS_SCORE"]),
    ("Variant", ["MOD_TRONBIN_BRANCH"]),
]
SMOOTHING_ABOUT = {
    "Off (sharp pixels)": "Square pixels, the original look.",
    "Scale2x": "Rounds off jagged diagonal edges; keeps the colours flat.",
    "Scale3x": "Like Scale2x with a finer result. Best at 3x or larger.",
}
FILES = [  # (settings key, label, folder or file)
    ("jzintv", "jzIntv (bin folder)", "folder"),
    ("bios", "Intellivision BIOS", "folder"),
    ("retail_rom", "TRON cartridge ROM", "file"),
    ("jzintv_test", "Test jzIntv build (optional, bin folder)", "folder"),
]
OPTIONAL_FILES = {"jzintv_test"}


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TRON Deadly Discs")
        self.resizable(False, False)
        self.paths, selected = tb.load_settings()
        options = tb.load_options()
        mods = {m[0]: m for m in tb.MODS}

        body = ttk.Frame(self, padding=12)
        body.grid(sticky="nsew")

        # Mods, grouped; descriptions in grey beside each
        box = ttk.LabelFrame(body, text="Mods", padding=8)
        box.grid(row=0, column=0, sticky="ew")
        self.vars = {}
        row = 0
        for heading, syms in MOD_GROUPS:
            ttk.Label(box, text=heading, font=("Segoe UI", 9, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(6 if row else 0, 0))
            row += 1
            for sym in syms:
                _, label, desc, _ = mods[sym]
                v = tk.BooleanVar(value=sym in selected)
                self.vars[sym] = v
                ttk.Checkbutton(box, text=label, variable=v).grid(row=row, column=0, sticky="w", padx=(10, 0))
                ttk.Label(box, text=desc, foreground="gray").grid(row=row, column=1, sticky="w", padx=(10, 0))
                row += 1
        presets = ttk.Frame(box)
        presets.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(presets, text="Retail (no mods)", command=lambda: self.preset([])).grid(row=0, column=0)
        ttk.Button(presets, text="Hack.cfg preset", command=lambda: self.preset(tb.HACK_PRESET)).grid(row=0, column=1, padx=6)

        # Display and controller
        opts = ttk.LabelFrame(body, text="Display and controller", padding=8)
        opts.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(opts, text="Screen").grid(row=0, column=0, sticky="w")
        self.display = tk.StringVar(value=options["display"])
        ttk.Combobox(opts, textvariable=self.display, values=list(tb.DISPLAYS), state="readonly",
                     width=26).grid(row=0, column=1, sticky="w", padx=(10, 0), pady=2)
        ttk.Label(opts, text="Pixel smoothing").grid(row=1, column=0, sticky="w")
        self.smoothing = tk.StringVar(value=options["smoothing"])
        ttk.Combobox(opts, textvariable=self.smoothing, values=list(tb.SMOOTHING), state="readonly",
                     width=26).grid(row=1, column=1, sticky="w", padx=(10, 0), pady=2)
        self.smoothing_about = ttk.Label(opts, foreground="gray")
        self.smoothing_about.grid(row=2, column=1, sticky="w", padx=(10, 0))
        self.smoothing.trace_add("write", lambda *_: self.update_smoothing_about())
        self.update_smoothing_about()

        self.right_stick = tk.BooleanVar(value=options["right_stick"] == "1")
        ttk.Checkbutton(opts, text="Right stick throws the disc", variable=self.right_stick).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(opts, foreground="gray", justify="left", text=(
            "Xbox-style controller: left stick moves, right stick or D-pad throws, A blocks.\n"
            "Keyboard: arrow keys move, number keys 1-9 throw.\n"
            "Quit Steam first (or turn off Steam Input for Xbox controllers).")).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))
        self.pad_status = ttk.Label(opts)
        self.pad_status.grid(row=5, column=0, columnspan=2, sticky="w", padx=(20, 0), pady=(4, 0))
        self.poll_controller()

        ttk.Label(opts, text="Emulator").grid(row=6, column=0, sticky="w", pady=(8, 0))
        self.emulator = tk.StringVar(value=options["emulator"])
        ttk.Combobox(opts, textvariable=self.emulator, values=list(tb.EMULATORS), state="readonly",
                     width=26).grid(row=6, column=1, sticky="w", padx=(10, 0), pady=(8, 0))
        ttk.Label(opts, foreground="gray", text="Test build: the jzIntv in the Files box's test folder.").grid(
            row=7, column=1, sticky="w", padx=(10, 0))

        # Files the launcher needs, each with a found / problem line
        files = ttk.LabelFrame(body, text="Files", padding=8)
        files.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.file_status = {}
        for i, (key, label, kind) in enumerate(FILES):
            ttk.Label(files, text=label).grid(row=2 * i, column=0, sticky="w")
            ttk.Button(files, text="Browse...", command=lambda k=key, kd=kind: self.browse(k, kd)).grid(
                row=2 * i, column=1, sticky="e", padx=(10, 0))
            status = ttk.Label(files, wraplength=470)
            status.grid(row=2 * i + 1, column=0, columnspan=2, sticky="w", padx=(10, 0), pady=(0, 4))
            self.file_status[key] = status
        files.columnconfigure(0, weight=1)
        self.refresh_files()

        # Buttons and status line
        bar = ttk.Frame(body)
        bar.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        bar.columnconfigure(0, weight=1)
        ttk.Button(bar, text="Verify", command=lambda: self.work(self.do_verify)).grid(row=0, column=1, padx=(0, 6))
        self.go = ttk.Button(bar, text="Play", command=lambda: self.work(self.do_play))
        self.go.grid(row=0, column=2)
        self.go.focus_set()
        self.bind("<Return>", lambda e: self.go.invoke())

        self.status = tk.StringVar(value="Ready.")
        ttk.Label(body, textvariable=self.status, wraplength=520).grid(row=4, column=0, sticky="w", pady=(8, 0))

    def preset(self, mods):
        for sym, v in self.vars.items():
            v.set(sym in mods)

    def selected(self):
        return [sym for sym, v in self.vars.items() if v.get()]

    def options(self):
        return {"display": self.display.get(), "smoothing": self.smoothing.get(),
                "right_stick": "1" if self.right_stick.get() else "0", "emulator": self.emulator.get()}

    def update_smoothing_about(self):
        self.smoothing_about.config(text=SMOOTHING_ABOUT.get(self.smoothing.get(), ""))

    def poll_controller(self):
        if right_stick.controller_connected():
            self.pad_status.config(text="Controller: connected", foreground="green")
        else:
            self.pad_status.config(text="Controller: none found (the keyboard works either way)",
                                   foreground="gray")
        self.after(2000, self.poll_controller)

    def browse(self, key, kind):
        current = Path(self.paths[key])
        if kind == "folder":
            chosen = filedialog.askdirectory(parent=self, initialdir=current if current.is_dir() else None)
        else:
            chosen = filedialog.askopenfilename(
                parent=self, initialdir=current.parent if current.parent.is_dir() else None,
                filetypes=[("Intellivision ROM", "*.bin *.int *.rom"), ("All files", "*.*")])
        if chosen:
            self.paths[key] = str(Path(chosen))
            tb.save_settings(self.paths, self.selected())
            self.refresh_files()

    def refresh_files(self):
        problems = tb.check_paths(self.paths)
        for key, label in self.file_status.items():
            problem = problems[key]
            if key in OPTIONAL_FILES and problem == "not set":
                label.config(text="Optional, not set", foreground="gray")
                continue
            label.config(text=("OK  " if not problem else "Problem: " + problem + "  ") + self.paths[key],
                         foreground="green" if not problem else "red")
        self.ready = not any(problems[k] for k in problems if k not in OPTIONAL_FILES)

    def work(self, fn):
        self.status.set("Working...")
        threading.Thread(target=self.guard, args=(fn,), daemon=True).start()

    def guard(self, fn):
        try:
            msg = fn()
        except Exception as e:  # show assembler/path errors in the window
            msg = f"Error: {e}"
        self.after(0, self.status.set, msg)

    def do_play(self):
        if not self.ready:
            return "Fix the files marked in red first (Browse... to point at them)."
        mods = self.selected()
        options = self.options()
        tb.assemble(mods, paths=self.paths)
        tb.save_settings(self.paths, mods)
        tb.save_options(options)
        tb.run(self.paths, options=options)
        return f"Running with {len(mods)} mod(s). build\\tron_mod.bin is the built ROM."

    def do_verify(self):
        if not self.ready:
            return "Fix the files marked in red first (Browse... to point at them)."
        lines = []
        ok = tb.verify(lines.append)
        return ("All checks passed. " if ok else "CHECK FAILED. ") + " | ".join(lines)


if __name__ == "__main__":
    Launcher().mainloop()
