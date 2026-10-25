"""Regenerate src/tron.asm from the retail ROM, dis1600 and src/labels.txt.

    py tools/disasm.py           write src/tron.asm and check it rebuilds retail

dis1600 does the code/data tracing; labels.txt adds entry points, data
ranges, names for code addresses and RAM, and comments.  dis1600 refers to
RAM and EXEC routines by name without defining them, so their EQUs are
recovered here from the instruction words dis1600 prints in its comments.

labels.txt lines (fields are whitespace separated, '#' starts a comment line):
    entry  5ABC                      dis1600 entry point (-e)
    data   5ABC-5ADF                 dis1600 data range (-d)
    code   5ABC  Name  [text]        label a ROM address; text goes on that line
    ram    015E  Name  [text]        name a RAM/IO address; text in the EQU block
    ext    1629  Name  [text]        name an EXEC (BIOS) routine dis1600 left unnamed
    note   5ABC  text                comment line(s) placed above that address

Unnamed branch labels (L_xxxx) inside a named routine become Routine_xxxx.
src/coverage.txt (tools/trace_session.py) adds every executed run start as
a dis1600 entry point.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tron_build as tb  # noqa: E402

LABELS = tb.SRC / "labels.txt"
COVERAGE = tb.SRC / "coverage.txt"
OUT = tb.SRC / "tron.asm"
ADDR_COMMENT = re.compile(r";\s*([0-9A-F]{4})\b")
LABEL_DEF = re.compile(r"^([.A-Za-z_][\w.]*):\s*$")
SYMBOL = re.compile(r"(?<![\w.$])(L_[0-9A-F]{4}|G_[0-9A-F]{4}|X_\w+|\.[A-Z][\w.]*\w)")


def read_labels():
    hints = {"entry": [], "data": [], "code": {}, "ram": {}, "ext": {}, "note": {}}
    for n, line in enumerate(LABELS.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        kind, rest = (line.split(None, 1) + [""])[:2]
        if kind == "entry":
            hints["entry"].append(int(rest.split()[0], 16))
        elif kind == "data":
            a, b = rest.split()[0].split("-")
            hints["data"].append((int(a, 16), int(b, 16)))
        elif kind in ("code", "ram", "ext"):
            addr, name, text = (rest.split(None, 2) + ["", ""])[:3]
            hints[kind][int(addr, 16)] = (name, text.strip())
        elif kind == "note":
            addr, text = (rest.split(None, 1) + [""])[:2]
            hints["note"].setdefault(int(addr, 16), []).append(text.rstrip())
        else:
            sys.exit(f"labels.txt:{n}: unknown line kind '{kind}'")
    if COVERAGE.exists():
        for line in COVERAGE.read_text().splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[0] == "code":
                hints["entry"].append(int(parts[1], 16))
    names = [v[0] for k in ("code", "ram", "ext") for v in hints[k].values()]
    dupes = {x for x in names if names.count(x) > 1}
    if dupes:
        sys.exit("labels.txt: duplicate names: " + ", ".join(sorted(dupes)))
    return hints


def run_dis1600(hints, paths):
    flags = []
    for a in hints["entry"]:
        flags.append(f"-e0x{a:04X}")
    for a, b in hints["data"]:
        flags.append(f"-d0x{a:04X}-0x{b:04X}")
    with tempfile.TemporaryDirectory() as tmp:
        rom = Path(tmp) / "tron.bin"
        rom.write_bytes(Path(paths["retail_rom"]).read_bytes())
        out = Path(tmp) / "out.asm"
        r = subprocess.run([str(Path(paths["jzintv"]) / "dis1600.exe"), "-f", *flags,
                            str(rom), str(out)], capture_output=True, text=True)
        if not out.exists():
            sys.exit("dis1600 failed:\n" + r.stdout + r.stderr)
        return out.read_text().splitlines()


def jump_target(words):
    """Target of a J/JSR-family instruction from its three encoded words."""
    w2, w3 = words[1], words[2]
    return ((w2 & 0xFC) << 8) | (w3 & 0x3FF)


def resolve_symbols(lines):
    """Map every dis1600 symbol to its address: (defined in file, external)."""
    local, external = {}, {}
    pending = []
    for line in lines:
        m = LABEL_DEF.match(line)
        if m:
            pending.append(m[1])
            continue
        c = ADDR_COMMENT.search(line)
        if c and pending and not line.lstrip().startswith(";"):
            for name in pending:
                local[name] = int(c[1], 16)
            pending = []
        for sym in SYMBOL.findall(line.split(";")[0]):
            if sym in local or sym in external:
                continue
            if sym.startswith(("G_", "L_")):
                external[sym] = int(sym[2:], 16)
            elif c:
                words = [int(w, 16) for w in line.split(";", 1)[1].split()[1:4]
                         if re.fullmatch(r"[0-9A-F]{4}", w)]
                if len(words) == 3 and words[0] == 0x0004:
                    external[sym] = jump_target(words)
                elif len(words) >= 2:      # direct-mode operand (MVI/MVO/ADD...)
                    external[sym] = words[1]
    for name in local:
        external.pop(name, None)
    return local, external


def generate():
    paths = tb.load_settings()[0]
    hints = read_labels()
    lines = run_dis1600(hints, paths)
    local, external = resolve_symbols(lines)

    # dis1600 symbol -> final name
    rename = {}
    by_addr = {}
    for sym, addr in local.items():
        by_addr.setdefault(addr, []).append(sym)
    for addr, (name, _) in hints["code"].items():
        for sym in by_addr.get(addr, []):
            rename[sym] = name
    for sym, addr in external.items():
        if sym.startswith("G_") and addr in hints["ram"]:
            rename[sym] = hints["ram"][addr][0]
        elif not sym.startswith(("G_", "L_")) and addr in hints["ext"]:
            rename[sym] = hints["ext"][addr][0]
    # unnamed branch labels take the name of the routine they sit in
    owners = sorted(hints["code"].items())
    for sym, addr in local.items():
        if sym in rename or not sym.startswith("L_"):
            continue
        owner = [name for a, (name, _) in owners if a <= addr]
        if owner:
            rename[sym] = f"{owner[-1]}_{addr:04X}"

    code_names = {a: n for a, (n, _) in hints["code"].items()}
    ram_names = {a: n for a, (n, _) in hints["ram"].items()}
    sdbd = [False]
    pcrel = [None]

    def sub(text):
        """Rename symbols, name address-like immediates, realign comments."""
        code, sep, comment = text.partition(";")
        code = SYMBOL.sub(lambda m: rename.get(m[1], m[1]), code)
        op = code.split()
        imm = re.search(r"#\$([0-9A-F]{4})", code)
        if imm and op:
            val = int(imm[1], 16)
            name = None
            if sdbd[0] and val in code_names:
                name = code_names[val]
            elif op[0] in ("MVII", "CMPI") and val in ram_names:
                name = ram_names[val]
            if name:
                code = code.replace(imm[0], "#" + name)
        if pcrel[0] is not None and op[:1] == ["ADDI"] and imm:
            target = pcrel[0] + int(imm[1], 16)
            owner = [n for a, n in sorted(code_names.items()) if a <= target]
            if owner:
                base = max(a for a in code_names if a <= target)
                off = target - base
                comment += f"  -> {owner[-1]}" + (f"+{off}" if off else "")
        pcrel[0] = None
        if op[:1] == ["MOVR"] and op[1:2] == ["R7,"] and sep:
            c = ADDR_COMMENT.search(sep + comment)
            pcrel[0] = int(c[1], 16) + 1 if c else None
        sdbd[0] = op[:1] == ["SDBD"]
        if not sep:
            return code
        if code.strip():
            code = code.rstrip()
            code = f"{code:<47} " if len(code) < 48 else code + " "
        return code + sep + comment

    # drop dis1600's cross-reference trailer; split DECLE lines at named addresses
    cut = next((i for i, l in enumerate(lines) if "Branch cross-reference" in l), None)
    if cut is not None:
        lines = lines[:cut - 1]
    split = []
    for line in lines:
        m = re.match(r"(\s+DECLE\s+)([^;]+);\s*([0-9A-F]{4})\b(.*)", line)
        if m:
            words = [w.strip() for w in m[2].split(",") if w.strip()]
            start = int(m[3], 16)
            cuts = [i for i in range(1, len(words)) if start + i in hints["code"]
                    or start + i in hints["note"]]
            if cuts:
                for a, b in zip([0] + cuts, cuts + [len(words)]):
                    split.append(f"{m[1]}{', '.join(words[a:b]):<32}; {start + a:04X}")
                continue
        split.append(line)
    lines = split
    labelled = {local[s] for s in local}

    out = [
        ";; TRON Deadly Discs (Mattel, 1981) - retail CRC32 CA447BBD",
        ";; GENERATED by tools/disasm.py from dis1600 + src/labels.txt.",
        ";; Edit labels.txt (names, comments, code/data hints) and regenerate;",
        ";; put gameplay changes in mods.asm.",
        "",
        ";; ---- EXEC (BIOS) routines ----",
    ]
    for sym, addr in sorted(external.items(), key=lambda kv: kv[1]):
        if not sym.startswith(("G_", "L_")):
            text = hints["ext"].get(addr, ("", ""))[1]
            out.append(f"{rename.get(sym, sym):<20} EQU     ${addr:04X}"
                       + (f"   ; {text}" if text else ""))
    out += ["", ";; ---- RAM ----"]
    ram = {addr: (rename.get(sym, sym), "") for sym, addr in external.items()
           if sym.startswith("G_")}
    for addr, (name, text) in hints["ram"].items():
        ram[addr] = (name, text)
    for addr, (name, text) in sorted(ram.items()):
        out.append(f"{name:<20} EQU     ${addr:04X}" + (f"   ; {text}" if text else ""))
    for sym, addr in sorted(external.items()):
        if sym.startswith("L_"):          # branch into an undefined spot
            out.append(f"{sym:<20} EQU     ${addr:04X}")
    out.append("")

    pending_labels = []
    for line in lines:
        m = LABEL_DEF.match(line)
        if m:
            pending_labels.append(line)
            continue
        c = ADDR_COMMENT.search(line)
        addr = int(c[1], 16) if c and not line.lstrip().startswith(";") else None
        if addr is not None:
            for text in hints["note"].pop(addr, []):
                out.append(f";; {text}" if text else ";;")
            seen = set()
            for lab in pending_labels:
                name = rename.get(lab[:-1].strip(), lab[:-1].strip())
                if name not in seen:
                    out.append(f"{name}:")
                    seen.add(name)
            if addr in hints["code"] and addr not in labelled:
                out.append(f"{hints['code'][addr][0]}:")
                labelled.add(addr)
            pending_labels = []
            if addr in hints["code"] and hints["code"][addr][1]:
                line = f"{line}  {hints['code'][addr][1]}"
        elif pending_labels and line.strip():
            out.extend(pending_labels)
            pending_labels = []
        out.append(sub(line))
    out += ["", '        INCLUDE "mods.asm"', ""]

    missing = [a for a in hints["code"] if a not in labelled]
    OUT.write_text("\n".join(out))
    for a in missing:
        print(f"warning: code label at ${a:04X} is not on an instruction/data start")
    for a in hints["note"]:
        print(f"warning: note at ${a:04X} not placed")


def main():
    generate()
    retail = Path(tb.load_settings()[0]["retail_rom"]).read_bytes()
    built = tb.assemble([], "verify")
    if built != retail:
        diff = [hex(0x5000 + i // 2) for i in range(0, len(retail), 2)
                if built[i:i + 2] != retail[i:i + 2]]
        sys.exit(f"src/tron.asm does NOT rebuild retail; first diffs at {diff[:10]}")
    print("src/tron.asm regenerated; rebuilds retail byte-for-byte")


if __name__ == "__main__":
    main()
