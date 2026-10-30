"""Build, verify and run modded TRON Deadly Discs ROMs.

    py tools/tron_build.py verify                 check the source against known ROMs
    py tools/tron_build.py build [--mods a,b] [--run]
    py tools/tron_build.py run                    run the last build

Mods are switched by MOD_* symbols in src/mods.asm.  Each build writes
build/options.asm with every switch set to 0 or 1, then assembles
src/tron.asm with as1600.  Paths and the last mod selection live in
tron_settings.ini next to this repo's README.
"""
import argparse
import configparser
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
BUILD = ROOT / "build"
SETTINGS = ROOT / "tron_settings.ini"
HACK_CFG = ROOT / "Tron Deadly Discs (Hack).cfg"

RETAIL_SHA1 = "a84392c29a69a7bff5f1b521a0e836622405180a"   # CRC32 CA447BBD
TRONBIN_SHA1 = "06e17a0dfe69e18999df061253416d3909b50bde"  # CRC32 FF8C6079

# Defaults: jzIntv and the BIOS unpacked inside this folder.  Point these
# anywhere else in tron_settings.ini ([paths] section).
DEFAULT_PATHS = {
    "jzintv": str(ROOT / "jzintv" / "bin"),
    "bios": str(ROOT / "bios"),
    "retail_rom": str(ROOT / "TRON-Deadly-Discs_Intellivision_EN"
                      / "TRON - Deadly Discs (1981)(Mattel).bin"),
    "tronbin_rom": str(ROOT / "tron.bin"),
    "jzintv_test": "",      # optional second jzIntv bin folder, e.g. a build from source
}

# (symbol, label, description, on in Hack.cfg)
MODS = [
    ("MOD_COLORS", "Recolor", "Tron light blue, his disc blue, Warriors pink, enemy discs black", True),
    ("MOD_START_SCORE", "Start with big score", "Guards appear at once (score display still shows 0)", True),
    ("MOD_POINT_TIER", "First point tier 10,000", "First point-value tier raised from 5 to 1000", True),
    ("MOD_TOP_TIER", "Jump to top point tier", "Off in Hack.cfg", False),
    ("MOD_CROSS_SCORE", "Cross score words", "Score races into 9 figures (off in Hack.cfg)", False),
    ("MOD_RECOG_NO_SHIELD", "Recognizer: no shield", "Removes the shield graphic over the eye", True),
    ("MOD_RECOG_BIG_EYE", "Recognizer: bigger eye", "Eye is easier to hit", True),
    ("MOD_DEREZZED", "DEREZZED!", "Game-over text reads DEREZZED!", True),
    ("MOD_TRONBIN_BRANCH", "tron.bin branch", "Hit test at $56EB as in the variant ROM tron.bin", False),
]
MOD_NAMES = [m[0] for m in MODS]
HACK_PRESET = [m[0] for m in MODS if m[3]]


def load_settings():
    cp = configparser.ConfigParser()
    cp.optionxform = str
    cp.read(SETTINGS)
    paths = dict(DEFAULT_PATHS)
    if cp.has_section("paths"):
        paths.update(cp["paths"])
    mods = HACK_PRESET
    if cp.has_section("mods"):
        mods = [m for m in MOD_NAMES if cp["mods"].getboolean(m, fallback=False)]
    return paths, mods


def save_settings(paths, mods):
    cp = configparser.ConfigParser()
    cp.optionxform = str
    cp.read(SETTINGS)                       # keep [options]
    cp["paths"] = paths
    cp["mods"] = {m: "1" if m in mods else "0" for m in MOD_NAMES}
    with open(SETTINGS, "w") as f:
        cp.write(f)


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def assemble(mods, stem="tron_mod", paths=None):
    """Assemble with the given MOD_* switches on; return the .bin bytes."""
    paths = paths or load_settings()[0]
    if not (SRC / "tron.asm").exists():     # generated from the user's own ROM
        import disasm
        disasm.main()
    unknown = set(mods) - set(MOD_NAMES)
    if unknown:
        raise ValueError("unknown mods: " + ", ".join(sorted(unknown)))
    BUILD.mkdir(exist_ok=True)
    (BUILD / "options.asm").write_text(
        "".join(f"{m:<20} EQU     {int(m in mods)}\n" for m in MOD_NAMES))
    out = BUILD / f"{stem}.bin"
    lst = BUILD / f"{stem}.lst"
    as1600 = Path(paths["jzintv"]) / "as1600.exe"
    r = subprocess.run([str(as1600), "-o", str(out), "-l", str(lst),
                        "-i", str(SRC), "-i", str(BUILD), str(SRC / "tron.asm")],
                       capture_output=True, text=True)
    log = r.stdout + r.stderr
    errors = re.search(r"ERRORS DETECTED\s+(\d+)", log)
    warnings = re.search(r"WARNINGS\s+(\d+)", log)
    if r.returncode or not errors or errors[1] != "0" or warnings[1] != "0":
        raise RuntimeError(f"as1600 failed (see {lst}):\n{log}")
    return out.read_bytes()


def cfg_patches(include_commented):
    """[macro] 'p addr value' lines from Hack.cfg as {addr: value}."""
    patches = {}
    for line in HACK_CFG.read_text().splitlines():
        m = re.match(r"(;?)p ([0-9a-fA-F]+) ([0-9a-fA-F]+)", line)
        if m and (include_commented or not m[1]):
            patches[int(m[2], 16)] = int(m[3], 16)
    return patches


def apply_patches(rom, patches):
    rom = bytearray(rom)
    for addr, val in patches.items():
        i = (addr - 0x5000) * 2
        rom[i:i + 2] = val.to_bytes(2, "big")
    return bytes(rom)


def verify(log=print):
    """Check every mod assembles and the source matches the known ROMs."""
    paths = load_settings()[0]
    retail = Path(paths["retail_rom"]).read_bytes()
    if sha1(retail) != RETAIL_SHA1:
        raise RuntimeError(f"retail ROM hash mismatch: {paths['retail_rom']}")
    checks = [("no mods == retail ROM", [], retail)]
    tronbin = Path(paths["tronbin_rom"])
    if tronbin.exists() and sha1(tronbin.read_bytes()) == TRONBIN_SHA1:
        checks.append(("tron.bin branch == tron.bin", ["MOD_TRONBIN_BRANCH"],
                       tronbin.read_bytes()))
    if HACK_CFG.exists():
        checks.append(("Hack.cfg preset == retail + Hack.cfg", HACK_PRESET,
                       apply_patches(retail, cfg_patches(False))))
        checks.append(("preset + commented lines == retail + all Hack.cfg lines",
                       HACK_PRESET + ["MOD_TOP_TIER", "MOD_CROSS_SCORE"],
                       apply_patches(retail, cfg_patches(True))))
    ok = True
    for name, mods, expected in checks:
        good = assemble(mods, "verify") == expected
        ok &= good
        log(f"{'PASS' if good else 'FAIL'}  {name}")
    for m in MOD_NAMES:
        assemble([m], "verify")
    log(f"PASS  each of the {len(MOD_NAMES)} mods assembles on its own")
    return ok


# jzIntv flags for every run; controller bindings are in tron.kbd.
# SDL XInput axes: 0/1 left stick, 2 left trigger, 3/4 right stick, 5 right trigger.
# noac: jzIntv's autocentering (on by default on Windows) drifts after a stick is
# held, so a centred stick keeps reading as pushed and the controls lock up.
# The right stick is claimed as JS0B only so tron.kbd can unbind it: jzIntv never
# releases a stick direction that slides into the next, which jams keypad keys.
# right_stick.py drives the throw keys from it instead.
CONTROLLER_ARGS = ["--js0a=noac",
                   "--js0b=xaxis=3,yaxis=4,noac",
                   f"--kbdhackfile={Path(__file__).with_name('tron.kbd')}"]

# Display choices: label -> jzIntv window size (the game draws 320x200).
# "Fullscreen" uses the desktop resolution, so the monitor does not switch modes.
DISPLAYS = {
    "Window 2x (640 x 400)": "640x400",
    "Window 3x (960 x 600)": "960x600",
    "Window 4x (1280 x 800)": "1280x800",
    "Fullscreen": None,
}
# Pixel smoothing: label -> jzIntv --prescale number
SMOOTHING = {"Off (sharp pixels)": 0, "Scale2x": 1, "Scale3x": 2}
# Which jzintv.exe Play starts: label -> [paths] key of its bin folder.
# The assembler and disassembler always come from the stock folder.
EMULATORS = {"Stock jzIntv": "jzintv", "Test build": "jzintv_test"}

DEFAULT_OPTIONS = {"display": "Window 2x (640 x 400)", "smoothing": "Off (sharp pixels)",
                   "right_stick": "1", "emulator": "Stock jzIntv"}


def load_options():
    """[options] from tron_settings.ini (display, smoothing, right_stick, emulator)."""
    cp = configparser.ConfigParser()
    cp.optionxform = str
    cp.read(SETTINGS)
    options = dict(DEFAULT_OPTIONS)
    if cp.has_section("options"):
        options.update(cp["options"])
    if options["display"] not in DISPLAYS:
        options["display"] = DEFAULT_OPTIONS["display"]
    if options["smoothing"] not in SMOOTHING:
        options["smoothing"] = DEFAULT_OPTIONS["smoothing"]
    if options["emulator"] not in EMULATORS:
        options["emulator"] = DEFAULT_OPTIONS["emulator"]
    return options


def save_options(options):
    cp = configparser.ConfigParser()
    cp.optionxform = str
    cp.read(SETTINGS)
    cp["options"] = options
    with open(SETTINGS, "w") as f:
        cp.write(f)


def desktop_size():
    """Physical desktop resolution, whatever the Windows scaling setting."""
    import ctypes
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    dc = user32.GetDC(None)
    try:
        return gdi32.GetDeviceCaps(dc, 118), gdi32.GetDeviceCaps(dc, 117)  # DESKTOPHORZRES/VERTRES
    finally:
        user32.ReleaseDC(None, dc)


def jzintv_args(options=None):
    """jzIntv flags for the chosen display and smoothing, plus the controller setup."""
    options = options or load_options()
    size = DISPLAYS[options["display"]]
    if size:
        display = [f"-z{size}", "-f0"]
    else:
        display = ["-z%dx%d" % desktop_size(), "-f1"]
    return [*display, f"--prescale={SMOOTHING[options['smoothing']]}", *CONTROLLER_ARGS]


EXEC_SHA1 = "5a65b922b562cb1f57dab51b73151283f0e20c7a"
GROM_SHA1 = "f9608bb4ad1cfe3640d02844c7ad8e0bcd974917"


def check_paths(paths):
    """{'jzintv'|'bios'|'retail_rom'|'jzintv_test': problem or ''} for the launcher's file checks.
    jzintv_test is optional: 'not set' is only a problem when the Test build is selected."""
    def file_sha1(p):
        return sha1(p.read_bytes()) if p.is_file() else None

    jz = Path(paths["jzintv"])
    missing = [n for n in ("jzintv.exe", "as1600.exe", "dis1600.exe") if not (jz / n).is_file()]
    bios = Path(paths["bios"])
    bios_problems = []
    for name, want in (("exec.bin", EXEC_SHA1), ("grom.bin", GROM_SHA1)):
        got = file_sha1(bios / name)
        if got is None:
            bios_problems.append(f"no {name}")
        elif got != want:
            bios_problems.append(f"{name} is not the standard dump")
    rom = file_sha1(Path(paths["retail_rom"]))
    test = paths.get("jzintv_test", "")
    return {
        "jzintv_test": ("not set" if not test
                        else "" if (Path(test) / "jzintv.exe").is_file() else "missing jzintv.exe"),
        "jzintv": "missing " + ", ".join(missing) if missing else "",
        "bios": "; ".join(bios_problems),
        "retail_rom": ("file not found" if rom is None
                       else "" if rom == RETAIL_SHA1 else "not the retail ROM (CRC32 CA447BBD)"),
    }


def start_right_stick(jzintv):
    """Run right_stick.py alongside a jzIntv process; it exits with jzIntv."""
    return subprocess.Popen([sys.executable, str(Path(__file__).with_name("right_stick.py")),
                             str(jzintv.pid)], creationflags=subprocess.CREATE_NO_WINDOW)


def run(paths=None, rom=None, options=None):
    paths = paths or load_settings()[0]
    options = options or load_options()
    rom = rom or BUILD / "tron_mod.bin"
    bios = Path(paths["bios"])
    key = EMULATORS[options["emulator"]]
    problem = check_paths(paths)[key]
    if problem:
        raise RuntimeError(f"{options['emulator']}: {problem} ({paths.get(key) or 'no folder chosen'})")
    p = subprocess.Popen([str(Path(paths[key]) / "jzintv.exe"), *jzintv_args(options),
                          "-e", str(bios / "exec.bin"), "-g", str(bios / "grom.bin"),
                          str(rom)], cwd=BUILD)
    if options["right_stick"] == "1":
        start_right_stick(p)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["verify", "build", "run"])
    ap.add_argument("--mods", help="comma-separated MOD_* names, 'hack', or 'none' "
                    "(default: last selection in tron_settings.ini)")
    ap.add_argument("--run", action="store_true", help="start jzIntv after building")
    a = ap.parse_args()
    paths, mods = load_settings()
    needed = ["jzintv", "retail_rom"]
    if a.action == "run" or a.run:
        needed.append("bios")
    problems = check_paths(paths)
    missing = [f"{k}: {problems[k]} ({paths[k]})" for k in needed if problems[k]]
    if missing:
        sys.exit("Files not ready (set them in the launcher or tron_settings.ini [paths]):\n  "
                 + "\n  ".join(missing))
    if a.action == "verify":
        sys.exit(0 if verify() else 1)
    if a.action == "build":
        if a.mods:
            mods = {"hack": HACK_PRESET, "none": []}.get(
                a.mods.lower(), [m.strip() for m in a.mods.split(",")])
        assemble(mods, paths=paths)
        save_settings(paths, mods)
        print("built build/tron_mod.bin with:", ", ".join(mods) or "no mods")
    if a.action == "run" or a.run:
        run(paths)


if __name__ == "__main__":
    main()
