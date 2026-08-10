"""
tile_status.py

Every executed spray is saved as a full COPY of its processed toolpath
file, in data/executed/ -- so each record is self-contained: you can
see exactly what geometry actually ran, not just a pointer back to
data/processed/ (whose contents could later be overwritten or cleaned out).

data/processed/  -- what gets SENT to the robot (302's output, 304's input)
data/executed/   -- what ACTUALLY ran, saved after a successful spray.
                    tile_selector.py and all status/eligibility checks
                    read from here.

Filename encodes everything TileHistory needs, so status checks never
have to open/parse the COMPAS frame data inside:
    <YYYYMMDD>_<HHMMSS>_tile<N>_<water|substrate>.json
"""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXECUTED_DIR = ROOT / "data" / "executed"

TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

# Single source of truth -- tile_selector.py imports this. Change it
# HERE to scale up or down; nothing else needs editing.
TOTAL_TILES = 4


class SprayRecord:
    """One executed spray -- a full copy of the processed toolpath file
    that was actually sent to the robot, saved into data/executed/ with
    tile_id/spray_type/timestamp encoded in the filename."""

    def __init__(self, tile_id, spray_type, source_path, timestamp=None):
        self.tile_id = tile_id
        self.spray_type = spray_type  # "water" or "substrate"
        self.source_path = Path(source_path)
        self.timestamp = timestamp or datetime.now()

    def filename(self):
        return f"{self.timestamp.strftime(TIMESTAMP_FORMAT)}_tile{self.tile_id}_{self.spray_type}.json"

    def save(self):
        """Copies the actual processed toolpath file into data/executed/.
        Returns the new file's path."""
        EXECUTED_DIR.mkdir(parents=True, exist_ok=True)
        dest = EXECUTED_DIR / self.filename()
        shutil.copy2(self.source_path, dest)
        return dest

    @classmethod
    def from_filename(cls, path):
        """Parses tile_id/spray_type/timestamp back out of an executed
        file's name. Returns None if it doesn't match the pattern
        (e.g. leftover files from before this naming scheme)."""
        parts = path.stem.split("_")
        if len(parts) != 4:
            return None
        date_part, time_part, tile_part, spray_type = parts
        try:
            timestamp = datetime.strptime(f"{date_part}_{time_part}", TIMESTAMP_FORMAT)
            tile_id = int(tile_part.replace("tile", ""))
        except ValueError:
            return None
        return cls(tile_id, spray_type, source_path=path, timestamp=timestamp)

    @classmethod
    def load_all(cls):
        if not EXECUTED_DIR.is_dir():
            return []
        records = [cls.from_filename(f) for f in EXECUTED_DIR.glob("*.json")]
        return [r for r in records if r is not None]


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
        return sum(1 for r in matching if r.timestamp >= cutoff)

    def last_sprayed_at(self, spray_type):
        """Returns a datetime, or None if never sprayed."""
        matching = [r.timestamp for r in self.records if r.spray_type == spray_type]
        return max(matching) if matching else None

    def describe(self, window_hours=12):
        last = self.last_sprayed_at("water")
        last_str = last.strftime("%Y-%m-%d %H:%M:%S") if last else "never"
        return (
            f"Tile {self.tile_id} of {TOTAL_TILES} -- "
            f"watered {self.count('water', window_hours)}x in the last {window_hours}h "
            f"(last at {last_str}), "
            f"{self.count('water')}x total; "
            f"substrate sprayed {self.count('substrate')}x total"
        )

    @classmethod
    def for_tile(cls, tile_id):
        return cls(tile_id, SprayRecord.load_all())


if __name__ == "__main__":
    print(f"Executed records directory: {EXECUTED_DIR}\n")
    print("Current status, all tiles:")
    for tile_id in range(1, TOTAL_TILES + 1):
        print(" ", TileHistory.for_tile(tile_id).describe())