"""Play retail TRON under jzIntv's memory-attribute logger to map code vs data.

    py tools/trace_session.py          play; close the window when done
    py tools/trace_session.py --merge  only merge an existing build/trace/dump.atr

jzIntv records, per address, whether it was fetched as code or read as data.
The debugger script dumps that map every ~5 s (so closing the window at any
time keeps it); afterwards the cartridge part ($5000-$5FFF) is merged into
src/coverage.txt, which tools/disasm.py uses as code/data hints.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tron_build as tb  # noqa: E402

TRACE = tb.BUILD / "trace"
COVERAGE = tb.SRC / "coverage.txt"
CHUNKS = 120            # x ~5 s = ~10 min max; closing the window early is fine
STEPS = 500000          # debugger 'r' count per chunk (~5 s real time)
KINDS = ("code", "data", "dbdata")


def read_atr(path, lo=0x5000, hi=0x5FFF):
    """{addr: set(kinds)} for lo..hi from a dump.atr / coverage.txt."""
    cov = {}
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] in KINDS:
            a, b = int(parts[1], 16), int(parts[2], 16)
            for x in range(max(a, lo), min(b, hi) + 1):
                cov.setdefault(x, set()).add(parts[0])
    return cov


def write_coverage(cov):
    lines = ["# Cartridge addresses seen by jzIntv's attribute logger during play.",
             "# Merged by tools/trace_session.py; read by tools/disasm.py."]
    for kind in KINDS:
        addrs = sorted(a for a, k in cov.items() if kind in k)
        start = prev = None
        for a in addrs + [None]:
            if a is not None and prev is not None and a == prev + 1:
                prev = a
                continue
            if start is not None:
                lines.append(f"{kind:<6} {start:04X} {prev:04X}")
            start = prev = a
    COVERAGE.write_text("\n".join(lines) + "\n")


def merge():
    dump = TRACE / "dump.atr"
    if not dump.exists():
        sys.exit("no build/trace/dump.atr to merge")
    cov = read_atr(COVERAGE) if COVERAGE.exists() else {}
    before = sum(1 for k in cov.values() if "code" in k)
    for a, kinds in read_atr(dump).items():
        cov.setdefault(a, set()).update(kinds)
    write_coverage(cov)
    after = sum(1 for k in cov.values() if "code" in k)
    print(f"coverage: {after} code words (+{after - before}), {len(cov)} words touched")


def play():
    paths = tb.load_settings()[0]
    TRACE.mkdir(parents=True, exist_ok=True)
    (TRACE / "dump.atr").unlink(missing_ok=True)
    script = TRACE / "trace.txt"
    script.write_text("a\n" + f"r {STEPS}\nd\n" * CHUNKS + "q\n")
    bios = Path(paths["bios"])
    p = subprocess.Popen([str(Path(paths["jzintv"]) / "jzintv.exe"), "-d",
                          f"--script={script.name}", *tb.JZINTV_ARGS,
                          "-e", str(bios / "exec.bin"), "-g", str(bios / "grom.bin"),
                          paths["retail_rom"]], cwd=TRACE, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tb.start_right_stick(p)
    p.wait()
    merge()


if __name__ == "__main__":
    merge() if "--merge" in sys.argv else play()
