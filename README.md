# TRON Deadly Discs, modernized

Intellivision, Mattel 1981. Retail ROM: 4K words at `$5000-$5FFF`, CRC32 `CA447BBD`.

The goal: play a 1981 cartridge the way you'd expect to play a game today.
One launcher window sets everything up and starts the game:

- **Modern controls.** An Xbox-style controller works out of the box: left stick
  moves, right stick throws the disc. The original needs a 12-button keypad
  for that, which jzIntv's stock bindings handle badly.
- **Display options.** Window size, fullscreen, and pixel smoothing.
- **Optional mods.** Recolors, Recognizer tweaks, scoring changes and more, each
  one a checkbox. With no mods ticked, the build is byte-for-byte the retail
  game.
- **A labelled disassembly** that every mod is built from, so new tweaks can be
  written as source rather than raw byte patches.

**No game or BIOS files are included**: you supply your own, and the disassembly
(`src/tron.asm`) is generated from your ROM.

## What you need

- Windows with Python 3 (the `py` launcher).
- [jzIntv](http://spatula-city.org/~im14u2c/intv/) release 20200712, the
  **win32 SDL2** build (`jzintv-20200712-win32-sdl2.zip`). It includes the
  SDK-1600 tools (`as1600`, `dis1600`) this project uses. The SDL1 build numbers
  the controller axes differently and does not work with these settings.
- The Intellivision system ROMs:
  `exec.bin` (SHA-1 `5a65b922b562cb1f57dab51b73151283f0e20c7a`) and
  `grom.bin` (SHA-1 `f9608bb4ad1cfe3640d02844c7ad8e0bcd974917`).
- The TRON Deadly Discs cartridge ROM, 8192-byte `.bin`
  (SHA-1 `a84392c29a69a7bff5f1b521a0e836622405180a`, CRC32 `CA447BBD`).

## Setup

The launcher's **Files** box shows whether each file was found and has the
right hash. Use **Browse...** to point at them. By default it looks inside
this folder:

| File | Default location |
|---|---|
| jzIntv | `jzintv/bin/jzintv.exe` (unzip the release into `jzintv/`) |
| `exec.bin`, `grom.bin` | `bios/` |
| Cartridge ROM | `TRON-Deadly-Discs_Intellivision_EN/TRON - Deadly Discs (1981)(Mattel).bin` |

Paths you pick are saved in `tron_settings.ini` (`[paths]`) next to this README.

The first build generates `src/tron.asm` from your ROM and checks that it
reassembles to the exact same bytes.

## Run

Double-click `launch_tron.bat`. The launcher window has:

| Section | Options |
|---|---|
| Mods | Look, Scoring and Variant mods with a description of each; **Retail** and **Hack.cfg preset** buttons |
| Display and controller | Window 2x / 3x / 4x or fullscreen (at your desktop resolution); pixel smoothing (off, Scale2x, Scale3x); right stick throws on/off; whether a controller is connected; emulator (stock jzIntv or a test build) |
| Files | jzIntv, BIOS and cartridge ROM, each checked; optionally a second jzIntv bin folder to test, such as your own build from source |

**Play** (or Enter) builds the ROM with the ticked mods and starts jzIntv.
**Verify** checks that the source still rebuilds the known ROMs. Everything is
remembered in `tron_settings.ini`. From a shell:

```
py tools/tron_build.py verify
py tools/tron_build.py build --mods hack --run      # or none, or MOD_A,MOD_B
```

The built ROM is `build/tron_mod.bin` + `.cfg`. A shell `run` uses the display
and controller options last saved by the launcher.

## Controls (Xbox controller)

| Controller | TRON |
|---|---|
| Left stick | Move |
| Right stick or D-pad | Throw the disc (8 directions; TRON throws with the keypad) |
| A | Block / duck (keypad 5) |

Keyboard: arrow keys move, number keys 1-9 throw (jzIntv's defaults).

**Quit Steam first**, or turn off *Settings > Controller > Enable Steam Input for
Xbox controllers*. Steam Input turns the pad into keyboard/mouse input on the
desktop and steals focus, which leaves keys stuck in jzIntv.

How it works, for anyone adapting it:

- `tools/tron.kbd` binds every controller input explicitly, so none of jzIntv's
  built-in joystick defaults apply.
- jzIntv's stick events never release a direction that slides into the next one.
  That is fine for the disc (movement), but keypad keys stay held, pile up, and
  once 1 and 9 are both held the EXEC pauses the game (black screen). So jzIntv's
  right-stick events are unbound and `tools/right_stick.py`, started alongside
  jzIntv, reads the right stick through XInput and sends one number key per flick.
- jzIntv's stick autocentering (on by default on Windows) leaves a released stick
  reading as pushed, so it is turned off (`CONTROLLER_ARGS` in `tools/tron_build.py`).

## Layout

| Path | |
|---|---|
| `src/tron.asm` | Labelled disassembly, **generated** from your ROM (not in the repo); rebuilds it byte for byte |
| `src/labels.txt` | Names, comments and code/data hints that `tron.asm` is generated from |
| `src/coverage.txt` | Addresses jzIntv saw executed/read during play (code/data evidence) |
| `src/mods.asm` | One `IF MOD_x` block per mod, ORG'd over retail words |
| `tools/disasm.py` | dis1600 + labels.txt -> `src/tron.asm`, then checks it rebuilds retail |
| `tools/trace_session.py` | Play under jzIntv's attribute logger; merges into coverage.txt |
| `launch_tron.bat` | Opens the launcher (checks Python is installed) |
| `tools/tron_build.py` | Assemble, verify, run; display/controller options; file checks |
| `tools/tron_launcher.py` | The launcher window |
| `tools/right_stick.py` | Right stick -> throw keys (see Controls) |
| `tools/tron.kbd` | jzIntv controller bindings |
| `tron.bin`, `Tron Deadly Discs (Hack).cfg` | Optional third-party files `verify` also checks against, if present; not included |

Editing the disassembly: change `src/labels.txt`, run `py tools/disasm.py`. Gameplay
changes go in `mods.asm`, not `tron.asm`.

A `tron.bin` found online (CRC32 `FF8C6079`, alongside a disassembly made from it)
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
2. ~~Launcher with controller, display and mod options.~~ Done.
3. Test the `$56EB` variant in play to see what it changes.
4. Map gameplay in detail: disc physics, enemy kinds and AI, waves, Recognizer.
5. New mods on top of that map.

## Credits

The mods marked "Hack.cfg" in `src/mods.asm` (recolors, big starting score,
first point tier, Recognizer without shield / bigger eye, DEREZZED!) recreate the
`[macro]` patches in "Tron Deadly Discs (Hack).cfg", a jzIntv config found online
with no author named. If it's yours, open an issue and it will be credited here.

## License

The tools, labels, mods and docs in this repository are MIT licensed (see
`LICENSE`). That covers this project's own work only: TRON Deadly Discs, the
Intellivision EXEC/GROM and jzIntv belong to their respective owners, and none
of them are included here.
