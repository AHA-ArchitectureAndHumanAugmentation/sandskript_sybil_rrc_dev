"""
tile_status.py

Every spray is its own small JSON record in data/robot/ -- not one
aggregate file. Clean write per spray, doubles as a full audit trail.

Tile ID travels WITH the pipeline data itself (embedded in path.json,
carried through 301 -> 302 -> 304), not tracked as separate "currently
active" state -- that avoids any chance of it going out of sync with
which capture it actually belongs to.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECORDS_DIR = ROOT / "data" / "robot"

# Single source of truth -- tile_selector.py imports this. Change it
# HERE to scale up or down; nothing else needs editing.
TOTAL_TILES = 4


class SprayRecord:
    """One execution's record -- one file per spray, in data/robot/."""

    def __init__(self, tile_id, spray_type, timestamp=None, source_path=None):
        self.tile_id = tile_id
        self.spray_type = spray_type  # "water" or "substrate"
        self.timestamp = timestamp or datetime.now().isoformat(timespec="seconds")
        self.source_path = source_path

    def save(self):
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{self.timestamp.replace(':', '-')}_tile{self.tile_id}_{self.spray_type}.json"
        filepath = RECORDS_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=4)
        return filepath

    def to_dict(self):
        return {
            "tile_id": self.tile_id,
            "spray_type": self.spray_type,
            "timestamp": self.timestamp,
            "source_path": self.source_path,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["tile_id"], data["spray_type"], data["timestamp"], data.get("source_path"))

    @classmethod
    def load_all(cls):
        if not RECORDS_DIR.is_dir():
            return []
        return [cls.from_dict(json.loads(f.read_text(encoding="utf-8"))) for f in RECORDS_DIR.glob("*.json")]


class TileHistory:
    """A tile's own records, and what it can tell you about itself."""

    def __init__(self, tile_id, records):
        self.tile_id = tile_id
        self.records = [r for r in records if r.tile_id == tile_id]

    def count(self, spray_type, hours=None):
        matching = [r for r in self.records if r.spray_type == spray_type]
        if hours is None:
            return len(matching)
        cutoff = datetime.now() - timedelta(hours=hours)
        return sum(1 for r in matching if datetime.fromisoformat(r.timestamp) >= cutoff)

    def last_sprayed_at(self, spray_type):
        matching = [r.timestamp for r in self.records if r.spray_type == spray_type]
        return max(matching) if matching else "never"

    def describe(self, window_hours=12):
        return (
            f"Tile {self.tile_id} of {TOTAL_TILES} -- "
            f"watered {self.count('water', window_hours)}x in the last {window_hours}h "
            f"(last at {self.last_sprayed_at('water')}), "
            f"{self.count('water')}x total; "
            f"substrate sprayed {self.count('substrate')}x total"
        )

    @classmethod
    def for_tile(cls, tile_id):
        return cls(tile_id, SprayRecord.load_all())


if __name__ == "__main__":
    print(f"Records directory: {RECORDS_DIR}\n")
    print("Current status, all tiles:")
    for tile_id in range(1, TOTAL_TILES + 1):
        print(" ", TileHistory.for_tile(tile_id).describe())