"""
tile_selector.py

Picks a tile to work on next -- random pick, checked against eligibility,
retried on failure. Uses tile_status.TileHistory for the spray data.
"""

import json
import random
from datetime import datetime
from pathlib import Path

from tile_status import TileHistory, TOTAL_TILES

ROOT = Path(__file__).resolve().parent
SELECTIONS_DIR = ROOT / "data" / "tiles" / "selections"

TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

CURRENT_SPRAY_TYPE = "water"

MAX_WATER_SPRAYS_PER_WINDOW = 3
MAX_SUBSTRATE_SPRAYS_PER_WINDOW = 2
WINDOW_HOURS = 12

MAX_WATER_SPRAYS_TOTAL = None
MAX_SUBSTRATE_SPRAYS_TOTAL = None

_MAX_PER_WINDOW = {"water": MAX_WATER_SPRAYS_PER_WINDOW, "substrate": MAX_SUBSTRATE_SPRAYS_PER_WINDOW}
_MAX_TOTAL = {"water": MAX_WATER_SPRAYS_TOTAL, "substrate": MAX_SUBSTRATE_SPRAYS_TOTAL}


class SelectionRecord:
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
            raise ValueError(f"Unknown spray_type: {spray_type!r}")
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
                print(f"Tile {tile_id}: {total}/{self.max_total} {self.spray_type} sprays total -- lifetime cap reached.")
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
            print(f"WARNING: no tile passed eligibility -- falling back to tile {chosen}.")
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
    for tile_id in range(1, TOTAL_TILES + 1):
        print(" ", TileHistory.for_tile(tile_id).describe())
    for _ in range(5):
        selector.select()