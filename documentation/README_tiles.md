# Tile Tracking & Selection

Four planting tiles share the garden. After every real spray, this system
records what happened and automatically decides which tile to work on next.

## tile_status.py — what happened, and when

**`SprayRecord`** — one real execution's record. Not metadata pointing back
to another file: a **full copy** of the exact processed toolpath that ran,
so each record is self-contained even if `data/processed/` is later cleaned
out. Saved into `data/executed/`, named so the filename alone carries
everything needed for status checks:

```
20260810_120316_tile1_water.json
<timestamp>       <tile>  <water|substrate>
```

**`TileHistory`** — a tile's own stats, computed **live** from the files in
`data/executed/` every time it's asked, never from a stored counter that
could go stale or drift out of sync:

```powershell
python tile_status.py
```

```
Tile 2 of 4 -- watered 1x in the last 12h (last at 2026-08-10 10:00:24), 1x total; substrate sprayed 0x total
```

`TOTAL_TILES = 4` is the single source of truth for tile count — change it
here to scale up or down; `tile_selector.py` reads it from this file rather
than defining its own copy.

`data/robot/` is an **obsolete** earlier version of this same idea (small
metadata-only records, before the full-copy redesign) — nothing reads from
it anymore, safe to delete.

## tile_selector.py — what happens next

**`TileSelector`** — random pick, checked against eligibility, retried on
failure:

```
pick a random tile
  -> eligible?  -> done, that's the selection
  -> not eligible?  -> try a different random tile
  -> ALL tiles ineligible?  -> fall back to whichever was sprayed longest ago
```

Two independent kinds of limit, set separately for water and substrate:

- **Rate limit** (`MAX_WATER_SPRAYS_PER_WINDOW`,
  `MAX_SUBSTRATE_SPRAYS_PER_WINDOW`, shared `WINDOW_HOURS`) — a tile becomes
  temporarily ineligible if it's been sprayed too many times recently, and
  becomes eligible again once enough time passes.
- **Lifetime cap** (`MAX_WATER_SPRAYS_TOTAL`, `MAX_SUBSTRATE_SPRAYS_TOTAL`)
  — optional, `None` by default. If set, a tile becomes **permanently**
  ineligible once it hits this count, ever.

`CURRENT_SPRAY_TYPE` is a manual switch (`"water"` or `"substrate"`) —
matches `SPRAY_TYPE` in `304_send_to_robot.py`. Whichever type is active
determines which limits apply.

**`SelectionRecord`** — every selection is saved to
`data/tiles/selections/`, same pattern as `SprayRecord`, so "what tile is
next" can be checked at any later point, not just caught live in a
terminal:

```powershell
python -c "from tile_selector import SelectionRecord; r = SelectionRecord.latest(); print(f'Tile {r.tile_id}, {r.spray_type}, selected at {r.timestamp}')"
```

## The full loop

`304_send_to_robot.py`, right after a real spray:

```python
record_path = SprayRecord(toolpath.tile_id, SPRAY_TYPE, source_path=str(data_file)).save()
next_tile = TileSelector(spray_type=SPRAY_TYPE).select()
with TileAnnouncer() as announcer:
    announcer.announce(next_tile)
```

Record → select → announce, in that order, only after a genuinely
completed spray (`TEST_STEP == 5` in execute mode, or as a deliberate demo
stand-in when `RECORD_IN_PREVIEW = True` — see README_testing.md).

## Still open

- Watering and substrate spraying currently only differ by `spray_type` and
  its separate limits. A physically different toolpath (e.g. a simple
  left-to-right sweep for watering, versus the point-by-point path used for
  substrate) is not yet built — a real, separate future task if the two
  need genuinely different motion, not just different bookkeeping.
- Spray protocol itself (how many layers, timing between rounds, the actual
  rules behind "spray x3") is still an open domain question, not a code
  question — see the project tracking doc.
