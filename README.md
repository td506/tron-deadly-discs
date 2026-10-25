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
| `src/tron.asm` | Labelled disassembly, **generated**; rebuilds the retail ROM byte for byte |
| `src/labels.txt` | Names, comments and code/data hints that `tron.asm` is generated from |
| `src/coverage.txt` | Addresses jzIntv saw executed/read during play (code/data evidence) |
| `src/mods.asm` | One `IF MOD_x` block per mod, ORG'd over retail words |
| `tools/disasm.py` | dis1600 + labels.txt -> `src/tron.asm`, then checks it rebuilds retail |
| `tools/trace_session.py` | Play under jzIntv's attribute logger; merges into coverage.txt |
| `tools/tron_build.py` | Assemble, verify, run |
| `tools/tron_launcher.py` | Mod picker window |
| `tron.asm`, `tron.bin`, `*.zip`, `Tron Deadly Discs (Hack).cfg` | Downloaded originals, not tracked |

Editing the disassembly: change `src/labels.txt`, run `py tools/disasm.py`. Gameplay
changes go in `mods.asm`, not `tron.asm`.

The downloaded `tron.asm` was disassembled from `tron.bin` (CRC32 `FF8C6079`), which
differs from retail in one word: the branch at `$56EB` in `HitTest` goes to
`HitTest_No` instead of `HitTest_Yes` when the target's `State` is not 4.
`MOD_TRONBIN_BRANCH` restores the variant.

## Verified

- no mods == retail ROM
- `MOD_TRONBIN_BRANCH` == `tron.bin`
- Hack.cfg preset == retail + the active `[macro]` patches in Hack.cfg
- preset + `MOD_TOP_TIER` + `MOD_CROSS_SCORE` == retail + every Hack.cfg line

## Notes

The game runs under the Mattel EXEC (BIOS). The EXEC owns the main loop, moves
objects and detects collisions, and calls the cartridge through:

- the header (`CartHeader`): title hook, `Start`, graphics and GRAM init lists;
- `TimerTable`: periodic tasks (`Tick1`, `Tick5`, `Tick25`, `EnemyAI` every 60, two every 200);
- `CtrlDispatch` (`$035D` -> `CtrlTable`): `OnDisc`, `OnKey`;
- object descriptors (`Type*`): per-object handlers and collision tables.

Object records: 8 words at `$031D + 8n` (`ObjN_Flags/Type/X/Y/Vel/State/Timer/Speed`).
Objects pair up as figure + disc: 0 Tron, 1 Tron's disc, 2/4/6 enemies, 3/5/7 their
discs. During the Recognizer, objects 2-7 are its parts (eye = obj 4, shield = obj 5).
`MotionMask` (`$011A`) has a bit per object the EXEC is allowed to move.

Colour bytes (e.g. `Init_Tron`): colour = bits 0-2, +8 if bit 4 is set.
Score = `ScoreHi`*10000 + `ScoreLo`; `Level` (0-14) indexes `PointsByLevel` and
`LevelThresholds`.

Names whose comment ends in `?` are inferred from the code, not yet confirmed in play.
EXEC routine names (`X_VEL_DIR`, `X_MOTION_ON`, ...) come from disassembling
`exec.bin`; note dis1600's own `X_SET_BIT`/`X_CLR_BIT` names are swapped.

## Plan

1. ~~Label the source.~~ Done; refine the `?` names with play traces.
2. Test the `$56EB` variant in play to see what it changes.
3. Map gameplay in detail: disc physics, enemy kinds and AI, waves, Recognizer.
4. New mods on top of that map.
