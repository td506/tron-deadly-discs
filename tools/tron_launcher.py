"""Pick TRON Deadly Discs mods, then build and run in jzIntv."""
import threading
import tkinter as tk
from tkinter import ttk

import tron_build as tb


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TRON Deadly Discs - Mods")
        self.resizable(False, False)
        self.paths, selected = tb.load_settings()
        self.vars = {}

        box = ttk.LabelFrame(self, text="Mods", padding=8)
        box.grid(row=0, column=0, columnspan=4, padx=10, pady=(10, 4), sticky="ew")
        for row, (sym, label, desc, _) in enumerate(tb.MODS):
            v = tk.BooleanVar(value=sym in selected)
            self.vars[sym] = v
            ttk.Checkbutton(box, text=label, variable=v).grid(row=row, column=0, sticky="w")
            ttk.Label(box, text=desc, foreground="gray").grid(row=row, column=1, sticky="w", padx=(10, 0))

        ttk.Button(self, text="Retail (none)", command=lambda: self.preset([])).grid(row=1, column=0, padx=(10, 2), pady=4, sticky="ew")
        ttk.Button(self, text="Hack.cfg preset", command=lambda: self.preset(tb.HACK_PRESET)).grid(row=1, column=1, padx=2, pady=4, sticky="ew")
        ttk.Button(self, text="Verify", command=lambda: self.work(self.do_verify)).grid(row=1, column=2, padx=2, pady=4, sticky="ew")
        self.go = ttk.Button(self, text="Build && Run", command=lambda: self.work(self.do_build))
        self.go.grid(row=1, column=3, padx=(2, 10), pady=4, sticky="ew")
        self.go.focus_set()
        self.bind("<Return>", lambda e: self.go.invoke())

        self.status = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self.status, wraplength=520).grid(row=2, column=0, columnspan=4, padx=10, pady=(4, 10), sticky="w")

    def preset(self, mods):
        for sym, v in self.vars.items():
            v.set(sym in mods)

    def selected(self):
        return [sym for sym, v in self.vars.items() if v.get()]

    def work(self, fn):
        self.status.set("Working...")
        threading.Thread(target=self.guard, args=(fn,), daemon=True).start()

    def guard(self, fn):
        try:
            msg = fn()
        except Exception as e:  # show assembler/path errors in the window
            msg = f"Error: {e}"
        self.after(0, self.status.set, msg)

    def do_build(self):
        mods = self.selected()
        tb.assemble(mods, paths=self.paths)
        tb.save_settings(self.paths, mods)
        tb.run(self.paths)
        return f"Running with {len(mods)} mod(s). build\\tron_mod.bin is the built ROM."

    def do_verify(self):
        lines = []
        ok = tb.verify(lines.append)
        return ("All checks passed. " if ok else "CHECK FAILED. ") + " | ".join(lines)


if __name__ == "__main__":
    Launcher().mainloop()
