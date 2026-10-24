# TRON Deadly Discs mods

Intellivision, Mattel 1981. Retail ROM: 4K words at `$5000-$5FFF`, CRC32 `CA447BBD`.

## Run

`launch_tron.bat` opens a window: tick mods, then **Build & Run**. **Verify** checks
the source still rebuilds the known ROMs. From a shell:

```
py tools/tron_build.py verify
py tools/tron_build.py build --mods hack --run      # or none, or MOD_A,MOD_B
```

The built ROM is `build/tron_mod.bin` + `.cfg`. Paths and the last selection are
saved in `tron_settings.ini`.

Requires jzIntv/SDK-1600 (`D:\RetroGames\tools\jzintv`, release 20200712) and the
system ROMs `exec.bin` + `grom.bin` (path in `tron_settings.ini`).

## Layout

| Path | |
|---|---|
| `src/tron.asm` | Full disassembly; rebuilds the retail ROM byte for byte |
| `src/mods.asm` | One `IF MOD_x` block per mod, ORG'd over retail words |
| `tools/tron_build.py` | Assemble, verify, run |
| `tools/tron_launcher.py` | Mod picker window |
| `tron.asm`, `tron.bin`, `*.zip`, `Tron Deadly Discs (Hack).cfg` | Downloaded originals, not tracked |

`tron.asm` was disassembled from `tron.bin` (CRC32 `FF8C6079`), which differs from
retail in one word: the branch at `$56EB` in `L_56CE` (a hit test that returns its
result in carry) goes to `CLRC` instead of `SETC` when the object type at R1+5 is
not 4. `src/tron.asm` uses the retail word; `MOD_TRONBIN_BRANCH` restores the variant.

## Verified

- no mods == retail ROM
- `MOD_TRONBIN_BRANCH` == `tron.bin`
- Hack.cfg preset == retail + the active `[macro]` patches in Hack.cfg
- preset + `MOD_TOP_TIER` + `MOD_CROSS_SCORE` == retail + every Hack.cfg line

## Plan

1. Test the `$56EB` variant in play to see what it changes.
2. Label the source: name RAM variables (`$015E`, `$015F`, `$0317/$0318` score…),
   routines, and the object/MOB tables; decode remaining `DECLE` runs into code.
3. Map gameplay: player movement, disc physics, enemy types and AI, wave/level
   progression, Recognizer, scoring.
4. New mods on top of that map.
