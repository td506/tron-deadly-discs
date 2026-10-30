# Open questions

## Tron's speed field ($0324) sets how fast he runs (next: MOD_TRON_SPEED)

- **Claim:** `SetTronSpeedByLevel` ($5452) writes Tron's running speed at the start of each wave: $0F below
  level 8, $14 for levels 8-13, $19 from level 14, as the same byte in both halves of `Obj0_Speed` ($0324).
  Enemy speeds are set separately by `SpawnWave`, so raising these three values speeds up Tron only.
- **Evidence:** read from the disassembly only. The value is handed to EXEC routines that compute movement,
  which have not been traced. `SyncSpeedBytes` ($5437) nudges X/Y by 5 and sets state $50 when the two halves
  differ; what triggers that (getting hit? blocking?) is unknown.
- **Affects:** the planned `MOD_TRON_SPEED` (+25%: $0F/$14/$19 -> $13/$19/$1F, at the immediates in $5452-$5461);
  whether it has side effects on knock-back, blocking or wall collisions.
- **Cheapest way to settle:** run the same scripted input (jzintv-hd's `JZINTV_HD_INPUT`) on retail and on the
  mod, log Tron's position from RAM each frame, and compare distance covered; then play a few waves.
