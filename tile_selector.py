#!/usr/bin/env python3
"""
tile_selector.py

Picks a tile to work on next -- random choice, checked against
eligibility rules, retried with a different tile if it fails. Uses
tile_status.TileHistory for the actual spray data (step 1).

CURRENT_SPRAY_TYPE is a manual switch for now -- matches SPRAY_TYPE in
304_send_to_robot.py. Eligibility and the fallback below both respect
whichever type is active; water and substrate keep fully separate
limits and separate "least recently sprayed" tracking.

No geometry here -- tiles are still just integers 1..TOTAL_TILES.

FALLBACK: if every tile fails the eligibility check, picks whichever
was sprayed (of the active type) longest ago and prints a clear
warning, rather than stalling or silently violating the limit.
"""

import random

from tile_status import TileHistory
from tile_status import TOTAL_TILES  # single source of truth -- change it in tile_status.py, not here

CURRENT_SPRAY_TYPE = "water"  # "water" or "substrate" -- manual switch for now

MAX_WATER_SPRAYS_PER_WINDOW = 3        # adjustable
MAX_SUBSTRATE_SPRAYS_PER_WINDOW = 2    # adjustable
WINDOW_HOURS = 12                      # adjustable -- shared by both spray types for now

_MAX_PER_WINDOW = {
    "water": MAX_WATER_SPRAYS_PER_WINDOW,
    "substrate": MAX_SUBSTRATE_SPRAYS_PER_WINDOW,
}


class TileSelector:
    def __init__(self, spray_type=CURRENT_SPRAY_TYPE, total_tiles=TOTAL_TILES, window_hours=WINDOW_HOURS):
        if spray_type not in ("water", "substrate"):
            raise ValueError(f"Unknown spray_type: {spray_type!r} -- use 'water' or 'substrate'.")
        self.spray_type = spray_type
        self.total_tiles = total_tiles
        self.window_hours = window_hours
        self.max_per_window = _MAX_PER_WINDOW[spray_type]

    def is_eligible(self, tile_id):
        history = TileHistory.for_tile(tile_id)
        recent = history.count(self.spray_type, hours=self.window_hours)
        return recent < self.max_per_window

    def select(self):
        candidates = list(range(1, self.total_tiles + 1))
        random.shuffle(candidates)

        for tile_id in candidates:
            if self.is_eligible(tile_id):
                return tile_id
            print(f"Tile {tile_id} not eligible for {self.spray_type} -- trying another.")

        fallback = self._least_recently_sprayed(candidates)
        print(f"WARNING: no tile passed the {self.spray_type} eligibility check -- "
              f"falling back to tile {fallback} (sprayed longest ago).")
        return fallback

    def _least_recently_sprayed(self, tile_ids):
        def sort_key(tile_id):
            last = TileHistory.for_tile(tile_id).last_sprayed_at(self.spray_type)
            return "" if last == "never" else last  # "never" sorts before any real timestamp
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
        chosen = selector.select()
        print(f"  -> Selected tile {chosen}\n")