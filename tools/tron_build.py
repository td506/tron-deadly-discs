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

DEFAULT_PATHS = {
    "jzintv": r"D:\RetroGames\tools\jzintv\bin",
    "bios": r"D:\RetroGames\Intv\Intellivision BIOS Set\Intellivision BIOS Set",
    "retail_rom": str(ROOT / "TRON-Deadly-Discs_Intellivision_EN"
                      / "TRON - Deadly Discs (1981)(Mattel).bin"),
    "tronbin_rom": str(ROOT / "tron.bin"),
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
    cp["paths"] = paths
    cp["mods"] = {m: "1" if m in mods else "0" for m in MOD_NAMES}
    with open(SETTINGS, "w") as f:
        cp.write(f)


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def assemble(mods, stem="tron_mod", paths=None):
    """Assemble with the given MOD_* switches on; return the .bin bytes."""
    paths = paths or load_settings()[0]
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
JZINTV_ARGS = ["-z640x400",           # window at 2x the default 320x200
               "--js0a=noac",
               "--js0b=xaxis=3,yaxis=4,noac",
               f"--kbdhackfile={Path(__file__).with_name('tron.kbd')}"]


def start_right_stick(jzintv):
    """Run right_stick.py alongside a jzIntv process; it exits with jzIntv."""
    return subprocess.Popen([sys.executable, str(Path(__file__).with_name("right_stick.py")),
                             str(jzintv.pid)], creationflags=subprocess.CREATE_NO_WINDOW)


def run(paths=None, rom=None):
    paths = paths or load_settings()[0]
    rom = rom or BUILD / "tron_mod.bin"
    bios = Path(paths["bios"])
    p = subprocess.Popen([str(Path(paths["jzintv"]) / "jzintv.exe"), *JZINTV_ARGS,
                          "-e", str(bios / "exec.bin"), "-g", str(bios / "grom.bin"),
                          str(rom)], cwd=BUILD)
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
