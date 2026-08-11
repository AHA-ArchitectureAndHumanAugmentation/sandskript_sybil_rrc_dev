"""
tile_status.py

Spray history for eligibility checks lives in ONE file:
data/tiles/tile_status.json -- read and rewritten on every spray, so it's
always current and fast to check.

data/executed/ is UNCHANGED -- still a full copy of every executed
toolpath, the real audit trail. tile_status.json is a fast INDEX built
from that trail, not a replacement for it. If it's ever lost or looks
wrong, rebuild_from_executed() regenerates it from data/executed/ directly.

Trade-off, stated plainly: this reintroduces one read-modify-write per
spray -- the exact pattern data/executed/'s per-file design was built to
avoid, back when concurrent writers were the concern. In practice one
robot only runs one spray at a time, so the real risk is low -- but it's
not zero if something else writes at the same moment.
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS_PATH = ROOT / "data" / "tiles" / "tile_status.json"
EXECUTED_DIR = ROOT / "data" / "executed"

TOTAL_TILES = 4


def _empty_status():
    return {str(t): {"water_sprays": [], "substrate_sprays": []} for t in range(1, TOTAL_TILES + 1)}


def _load():
    if not STATUS_PATH.is_file():
        return _empty_status()
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def _save(status):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=4), encoding="utf-8")


def record_spray(tile_id, spray_type, timestamp=None):
    """Appends one timestamp for this tile/type, saves, returns it."""
    status = _load()
    ts = (timestamp or datetime.now()).isoformat(timespec="seconds")
    key = f"{spray_type}_sprays"
    status.setdefault(str(tile_id), {"water_sprays": [], "substrate_sprays": []})
    status[str(tile_id)].setdefault(key, [])
    status[str(tile_id)][key].append(ts)
    _save(status)
    return ts


class TileHistory:
    """A tile's own stats, read from the single status file. Same public
    interface as before -- tile_selector.py needs no changes."""

    def __init__(self, tile_id, status=None):
        self.tile_id = tile_id
        self._entry = (status or _load()).get(str(tile_id), {"water_sprays": [], "substrate_sprays": []})

    def count(self, spray_type, hours=None):
        timestamps = self._entry.get(f"{spray_type}_sprays", [])
        if hours is None:
            return len(timestamps)
        cutoff = datetime.now() - timedelta(hours=hours)
        return sum(1 for ts in timestamps if datetime.fromisoformat(ts) >= cutoff)

    def last_sprayed_at(self, spray_type):
        timestamps = self._entry.get(f"{spray_type}_sprays", [])
        return datetime.fromisoformat(max(timestamps)) if timestamps else None

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
        return cls(tile_id)


class SprayRecord:
    """Same public interface as before -- 304_send_to_robot.py needs no
    changes. Still saves the full geometry copy to data/executed/; now
    also updates tile_status.json in the same call."""

    def __init__(self, tile_id, spray_type, source_path, timestamp=None):
        self.tile_id = tile_id
        self.spray_type = spray_type
        self.source_path = Path(source_path)
        self.timestamp = timestamp or datetime.now()

    def save(self):
        EXECUTED_DIR.mkdir(parents=True, exist_ok=True)
        ts_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
        dest = EXECUTED_DIR / f"{ts_str}_tile{self.tile_id}_{self.spray_type}.json"
        shutil.copy2(self.source_path, dest)

        record_spray(self.tile_id, self.spray_type, self.timestamp)
        return dest


def rebuild_from_executed():
    """Recovery path: regenerates tile_status.json from data/executed/'s
    filenames, in case the status file is ever lost, corrupted, or just
    looks wrong."""
    status = _empty_status()
    if EXECUTED_DIR.is_dir():
        for f in sorted(EXECUTED_DIR.glob("*.json")):
            parts = f.stem.split("_")
            if len(parts) != 4:
                continue
            date_part, time_part, tile_part, spray_type = parts
            try:
                ts = datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S").isoformat(timespec="seconds")
                tile_id = tile_part.replace("tile", "")
            except ValueError:
                continue
            status.setdefault(tile_id, {"water_sprays": [], "substrate_sprays": []})
            status[tile_id].setdefault(f"{spray_type}_sprays", [])
            status[tile_id][f"{spray_type}_sprays"].append(ts)
    _save(status)
    print(f"Rebuilt {STATUS_PATH} from {EXECUTED_DIR}")
    return status


if __name__ == "__main__":
    print(f"Status file: {STATUS_PATH}\n")
    print("Current status, all tiles:")
    for tile_id in range(1, TOTAL_TILES + 1):
        print(" ", TileHistory.for_tile(tile_id).describe())