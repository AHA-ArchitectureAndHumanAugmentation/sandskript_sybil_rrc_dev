#!/usr/bin/env python3
"""
tile_selector.py

Picks a tile to work on next -- random choice, checked against
eligibility rules, retried with a different tile if it fails. Uses
tile_status.TileHistory for the actual spray data.

Two SEPARATE kinds of limit, both optional (set to None to disable):
- MAX_..._PER_WINDOW -- rate limit. Blocks a tile temporarily if it's
  been sprayed too many times within WINDOW_HOURS. Tile becomes
  eligible again once enough time passes.
- MAX_..._TOTAL -- lifetime cap. Blocks a tile PERMANENTLY once it's
  been sprayed this many times, ever. Worth thinking about whether
  this makes sense for "water" (probably not, if watering continues
  indefinitely) vs "substrate" (more likely, if it's a limited number
  of applications per grow cycle).

CURRENT_SPRAY_TYPE is a manual switch for now -- matches SPRAY_TYPE in
304_send_to_robot.py.

Every selection is saved as its own small record in data/tiles/selections/
-- same audit-trail pattern as SprayRecord in tile_status.py -- so you
can check which tile was chosen at any later point, not just catch it
live in the console.

No geometry here -- tiles are still just integers 1..TOTAL_TILES.

FALLBACK: if every tile fails the eligibility check, picks whichever
was sprayed (of the active type) longest ago and prints a clear
warning, rather than stalling or silently violating the limit.
"""

import json
import random
from datetime import datetime
from pathlib import Path

from tile_status import TileHistory, TIMESTAMP_FORMAT
from tile_status import TOTAL_TILES  # single source of truth -- change it in tile_status.py, not here

ROOT = Path(__file__).resolve().parent
SELECTIONS_DIR = ROOT / "data" / "tiles" / "selections"

CURRENT_SPRAY_TYPE = "water"  # "water" or "substrate" -- manual switch for now

MAX_WATER_SPRAYS_PER_WINDOW = 3        # adjustable
MAX_SUBSTRATE_SPRAYS_PER_WINDOW = 2    # adjustable
WINDOW_HOURS = 12                      # adjustable -- shared by both spray types for now

MAX_WATER_SPRAYS_TOTAL = None          # adjustable, or None to disable -- lifetime cap
MAX_SUBSTRATE_SPRAYS_TOTAL = None      # adjustable, or None to disable -- lifetime cap

_MAX_PER_WINDOW = {"water": MAX_WATER_SPRAYS_PER_WINDOW, "substrate": MAX_SUBSTRATE_SPRAYS_PER_WINDOW}
_MAX_TOTAL = {"water": MAX_WATER_SPRAYS_TOTAL, "substrate": MAX_SUBSTRATE_SPRAYS_TOTAL}


class SelectionRecord:
    """One selection event -- lets you check which tile was chosen
    without catching it live in a terminal. Same pattern as SprayRecord."""

    def __init__(self, tile_id, spray_type, timestamp=None):
        self.tile_id = tile_id
        self.spray_type = spray_type
        self.timestamp = timestamp or datetime.now()

    def filename(self):
        return f"{self.timestamp.strftime(TIMESTAMP_FORMAT)}_tile{self.tile_id}_{self.spray_type}.json"

    def save(self):
        SELECTIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = SELECTIONS_DIR / self.filename()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"tile_id": self.tile_id, "spray_type": self.spray_type, "timestamp": self.timestamp.isoformat()},
                f, indent=4,
            )
        return path

    @classmethod
    def latest(cls):
        """The most recently saved selection, or None if there isn't one yet."""
        if not SELECTIONS_DIR.is_dir():
            return None
        files = sorted(SELECTIONS_DIR.glob("*.json"))
        if not files:
            return None
        data = json.loads(files[-1].read_text(encoding="utf-8"))
        return cls(data["tile_id"], data["spray_type"], datetime.fromisoformat(data["timestamp"]))


class TileSelector:
    def __init__(self, spray_type=CURRENT_SPRAY_TYPE, total_tiles=TOTAL_TILES, window_hours=WINDOW_HOURS):
        if spray_type not in ("water", "substrate"):
            raise ValueError(f"Unknown spray_type: {spray_type!r} -- use 'water' or 'substrate'.")
        self.spray_type = spray_type
        self.total_tiles = total_tiles
        self.window_hours = window_hours
        self.max_per_window = _MAX_PER_WINDOW[spray_type]
        self.max_total = _MAX_TOTAL[spray_type]

    def is_eligible(self, tile_id):
        history = TileHistory.for_tile(tile_id)

        recent = history.count(self.spray_type, hours=self.window_hours)
        if recent >= self.max_per_window:
            print(f"Tile {tile_id}: {recent}/{self.max_per_window} {self.spray_type} sprays "
                  f"in the last {self.window_hours}h -- rate limit reached.")
            return False

        if self.max_total is not None:
            total = history.count(self.spray_type)
            if total >= self.max_total:
                print(f"Tile {tile_id}: {total}/{self.max_total} {self.spray_type} sprays total "
                      f"-- lifetime cap reached, permanently ineligible.")
                return False

        return True

    def select(self):
        candidates = list(range(1, self.total_tiles + 1))
        random.shuffle(candidates)

        chosen = None
        for tile_id in candidates:
            if self.is_eligible(tile_id):
                chosen = tile_id
                break
            print(f"Tile {tile_id} not eligible for {self.spray_type} -- trying another.")

        if chosen is None:
            chosen = self._least_recently_sprayed(candidates)
            print(f"WARNING: no tile passed the {self.spray_type} eligibility check -- "
                  f"falling back to tile {chosen} (sprayed longest ago).")

        record_path = SelectionRecord(chosen, self.spray_type).save()
        print(f"\n=== NEXT TILE: {chosen} ({self.spray_type}) -- saved to {record_path} ===\n")
        return chosen

    def _least_recently_sprayed(self, tile_ids):
        def sort_key(tile_id):
            last = TileHistory.for_tile(tile_id).last_sprayed_at(self.spray_type)
            return datetime.min if last is None else last
        return min(tile_ids, key=sort_key)


if __name__ == "__main__":
    selector = TileSelector()
    print(f"Active spray type: {selector.spray_type}")
    print(f"Total tiles: {TOTAL_TILES}\n")

    print("Current status, all tiles:")
    for tile_id in range(1, TOTAL_TILES + 1):
        print(" ", TileHistory.for_tile(tile_id).describe())

    print(f"\nRunning selection 5 times ({selector.spray_type}):")
    for _ in range(5):
        selector.select()