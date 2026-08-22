"""
Sybil — the tiles.

WHAT THIS FILE IS FOR
Finds the tiles on disk and remembers which class each one is. Everything
else asks this file rather than guessing from filenames.

    A tiles    visitors draw on them. Substrate and water.
    B tiles    prepared before the exhibition. Water only once it opens,
               sprayed along the same path they were substrate-sprayed with.

WHY IT DISCOVERS RATHER THAN LISTS
The tiling is still changing — six tiles today, perhaps forty later, and the
split between A and B is not settled. So nothing here hard-codes a count.
Add or remove an .obj and the code follows.

NAMING
Both layouts work, so today's files keep running and tomorrow's just drop in:

    surfaces/tile_001.obj          class from DEFAULT_CLASS below
    surfaces/tile_A_001.obj        class A, from the name
    surfaces/tile_B_002.obj        class B, from the name
    surfaces/A/tile_001.obj        class A, from the folder
    surfaces/B/tile_002.obj        class B, from the folder

Lives in the RRC repo only:
    sandskript_sybil_rrc_dev/sybil/tiles.py
"""

from __future__ import annotations

import re

from sybil import config


# ==========================================================================
# SETTINGS
# ==========================================================================

SURFACES_DIR = config.SURFACES_DIR
# Where the tile meshes live. Subfolders named A and B are picked up
# automatically if they exist.

TILE_PATTERN = "tile_*.obj"
# Which files count as tiles. Anything in the folder not matching this is
# ignored, so notes and exports can sit alongside without confusing things.

DEFAULT_CLASS = "A"
# What to assume when a filename says nothing about its class — the current
# tile_001.obj style. Once everything is renamed tile_A_001 / tile_B_002 or
# split into A/ and B/ folders, this stops being used.
# Set to None instead to REFUSE unlabelled tiles rather than guessing. Safer
# once the renaming is done, because a stray old file would then be caught
# instead of quietly treated as an A tile.

B_PATH_DIR = config.REPO_ROOT / "data" / "tile_paths"
# Where each B tile's own toolpath lives, as tile_B_002.json and so on.
# These are the Grasshopper paths the tile was substrate-sprayed with before
# the exhibition, replayed with water during it.

WATER_ALL_B_EVERY_WINDOW = True
# True  = every B tile is watered in every maintenance window. Four times a
#         day each.
# False = they are shared across the day's windows, so each B tile is
#         watered once per day. A quarter of the robot time, and much less
#         water. Worth switching if the B tiles turn out not to need it.

# ==========================================================================


_NAME_CLASS = re.compile(r"tile_([AB])_", re.IGNORECASE)
_NAME_NUMBER = re.compile(r"(\d+)")


class Tile:
    """One tile: its id, its class, and where its mesh is."""

    def __init__(self, tile_id, tile_class, mesh_path):
        self.id = tile_id
        self.tile_class = tile_class
        self.mesh_path = mesh_path

    @property
    def is_a(self):
        return self.tile_class == "A"

    @property
    def is_b(self):
        return self.tile_class == "B"

    @property
    def path_file(self):
        """A B tile's own toolpath. None for A tiles, which get theirs from
        whatever the visitor draws."""
        if not self.is_b:
            return None
        return B_PATH_DIR / "{}.json".format(self.id)

    @property
    def has_path(self):
        path = self.path_file
        return path is not None and path.exists()

    def __repr__(self):
        return "Tile({}, class {})".format(self.id, self.tile_class)


def _class_from(path):
    """Work out a tile's class from its folder, then its filename."""
    parent = path.parent.name.upper()
    if parent in ("A", "B"):
        return parent

    match = _NAME_CLASS.search(path.stem)
    if match:
        return match.group(1).upper()

    return DEFAULT_CLASS


def _sort_key(tile):
    """Sort by class, then by the number in the name, so tile_010 comes
    after tile_009 rather than after tile_001."""
    numbers = _NAME_NUMBER.findall(tile.id)
    number = int(numbers[-1]) if numbers else 0
    return (tile.tile_class, number, tile.id)


class TileRegistry:
    """All the tiles, discovered from disk."""

    def __init__(self, surfaces_dir=None, pattern=None):
        self.surfaces_dir = SURFACES_DIR if surfaces_dir is None else surfaces_dir
        self.pattern = TILE_PATTERN if pattern is None else pattern
        self.tiles = []
        self.unlabelled = []
        self.discover()

    def discover(self):
        """Scan the folders and rebuild the list. Call again after adding
        meshes without restarting."""
        if not self.surfaces_dir.exists():
            raise FileNotFoundError(
                "Tile folder not found: {}".format(self.surfaces_dir)
            )

        found = []
        skipped = []

        # rglob so surfaces/A/ and surfaces/B/ are picked up too
        for mesh_path in sorted(self.surfaces_dir.rglob(self.pattern)):
            tile_class = _class_from(mesh_path)
            if tile_class is None:
                skipped.append(mesh_path)
                continue
            found.append(Tile(mesh_path.stem, tile_class, mesh_path))

        self.tiles = sorted(found, key=_sort_key)
        self.unlabelled = skipped
        return self.tiles

    # -- asking -----------------------------------------------------------

    @property
    def a_tiles(self):
        return [t for t in self.tiles if t.is_a]

    @property
    def b_tiles(self):
        return [t for t in self.tiles if t.is_b]

    def get(self, tile_id):
        for tile in self.tiles:
            if tile.id == tile_id:
                return tile
        return None

    def b_tiles_for_window(self, window_number, window_count=4):
        """Which B tiles to water in this maintenance window.

        With WATER_ALL_B_EVERY_WINDOW on, that is all of them, every time.
        With it off, they are split evenly across the day's windows so each
        B tile is watered once per day.
        """
        b_tiles = self.b_tiles
        if WATER_ALL_B_EVERY_WINDOW or not b_tiles:
            return b_tiles

        index = (window_number - 1) % window_count
        return [t for i, t in enumerate(b_tiles) if i % window_count == index]

    def missing_paths(self):
        """B tiles with no toolpath file. These cannot be watered."""
        return [t for t in self.b_tiles if not t.has_path]

    # -- reporting --------------------------------------------------------

    def describe(self):
        print("Tiles in {}".format(self.surfaces_dir))
        print("  {} total — {} class A, {} class B".format(
            len(self.tiles), len(self.a_tiles), len(self.b_tiles)))

        for tile in self.tiles:
            note = ""
            if tile.is_b:
                note = "  path: {}".format("ok" if tile.has_path else "MISSING")
            print("    {:<16} class {}{}".format(tile.id, tile.tile_class, note))

        if self.unlabelled:
            print("\n  {} file(s) skipped — no class in the name or folder:".format(
                len(self.unlabelled)))
            for path in self.unlabelled:
                print("    {}".format(path.name))
            print("  Set DEFAULT_CLASS in tiles.py, or rename them.")

        missing = self.missing_paths()
        if missing:
            print("\n  {} B tile(s) have no toolpath in {}:".format(
                len(missing), B_PATH_DIR))
            for tile in missing:
                print("    {}".format(tile.id))
            print("  These cannot be watered until their path is exported.")

    def estimate_watering_s(self, per_tile_s=200.0):
        """Roughly how long it takes to water every tile once."""
        return len(self.tiles) * per_tile_s


_registry = None


def registry():
    """The tiles, discovered on first use and kept afterwards."""
    global _registry
    if _registry is None:
        _registry = TileRegistry()
    return _registry


# --------------------------------------------------------------------------
# Check: python -m sybil.tiles
# --------------------------------------------------------------------------

if __name__ == "__main__":
    tiles = registry()
    tiles.describe()

    print("\n--- watering rotation ---")
    seconds = tiles.estimate_watering_s()
    print("  {} tiles at 200 s each = {:.0f} min".format(
        len(tiles.tiles), seconds / 60.0))
    print("  morning rotation has 60 min (09:00-10:00)")
    if seconds > 60 * 60:
        print("  WARNING — does not fit. Start earlier, or water faster.")
    else:
        print("  fits, with {:.0f} min to spare".format((3600 - seconds) / 60.0))

    print("\n--- B tiles per maintenance window ---")
    for window in range(1, 5):
        chosen = tiles.b_tiles_for_window(window)
        names = ", ".join(t.id for t in chosen) if chosen else "none"
        print("  window {}: {} tile(s) — {}".format(window, len(chosen), names))

    print("\ntiles ok")
