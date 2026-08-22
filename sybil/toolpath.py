"""
Sybil — toolpath geometry.

WHAT THIS FILE IS FOR
Holds a list of frames (positions + orientations) and knows how to make
useful variations of itself:

    safe_frame()               one point pulled back from the surface
    with_approach_and_retract()  adds a safe point at each end
    with_standoff()            the whole path pulled back — used for watering
    lanes()                    the path copied downward a few times

Nothing here talks to the robot. It is pure geometry, so it can be tested
on any machine.

Lives in the RRC repo only:
    sandskript_sybil_rrc_dev/sybil/toolpath.py
"""

from __future__ import annotations

from compas.data import json_load
from compas.geometry import Frame, Vector

from sybil import config
from fixed_geometry import SPHERE_CENTER


# ==========================================================================
# SETTINGS
# ==========================================================================

# --- Lane stepping -------------------------------------------------------
#
# The visitor draws one line. The robot sprays it several times, each copy
# shifted slightly downward, so the finished mark has some width instead of
# being a single thin stripe. The copies overlap on purpose.

LANE_COUNT = 4
# How many copies of the path to spray, including the original.
# 1 = spray the line once, exactly as drawn, no widening.
# More = a wider, denser mark, and a proportionally longer cycle time.
# Four copies takes four times as long as one — this is the setting most
# likely to break the schedule if you raise it.

LANE_OFFSET_MM = 30.0
# How far apart the copies are, in millimetres.
# Small (10–30) = the copies overlap heavily and read as one thick line.
# Large (100+) = separate visible stripes with gaps between them.
# 0 = every copy lands on top of the original, building thickness instead
# of width.

LANE_DIRECTION = Vector(0, 0, -1)
# Which way the copies step. (0, 0, -1) is straight down, toward the floor,
# so the mark grows downward from what the visitor drew.
# Change to (0, 0, 1) to grow upward, or give it any direction you like.
# It is normalised before use, so the length of this vector does not matter.

LANES_FOLLOW_SURFACE = True
# True  = each copy is stepped down and then put back at the right distance
#         from whatever part of the net is now underneath it. The lane
#         follows the curve, so it cannot drift into the surface.
# False = each copy is simply moved through space. Fine on a flat wall,
#         WRONG on a curved net — lanes will dig in where it bulges toward
#         you and lift off where it falls away.
# Leave this True unless you are testing without the net mesh present.

LANES_ORIENT_TO_SURFACE = True
# True  = each frame is turned to face the net square-on at its new
#         position, so the spray hits the surface straight.
# False = every frame keeps the orientation it was drawn with.
# Only has an effect when LANES_FOLLOW_SURFACE is True.


# --- Watering ------------------------------------------------------------

WATER_STANDOFF_MM = 700.0
# How far the nozzle pulls back from the net when watering, measured along
# the surface normal at each point.
# Watering uses the SAME path as spraying, just from further away, so the
# mist spreads out and falls gently instead of blasting the seedlings.
# Larger = gentler and wider, but eventually the arm cannot reach.
# Smaller = a harder, more concentrated jet of water.


# --- Filtering -----------------------------------------------------------

MIN_FRAGMENT_MM = 200.0
# The shortest path worth spraying, in millimetres.
# After a path is trimmed to fit inside its tile, the leftover pieces can be
# very short. Spraying a 3 cm stub costs a full approach and retract for
# almost no mark, so anything under this length is dropped.
# Lower = more small marks, slower day. Higher = only bold strokes survive.

# ==========================================================================


def _frame_facing(point, normal, like):
    """A frame at `point` turned to face along `normal`, keeping as much of
    `like`'s twist about that axis as possible."""
    z = normal.copy()
    if z.length > 1e-9:
        z.unitize()

    x = like.xaxis.copy()
    # Remove whatever part of the old x-axis points along the new normal,
    # so x stays perpendicular to it.
    x = x - z * x.dot(z)
    if x.length < 1e-6:
        x = like.yaxis.copy()
        x = x - z * x.dot(z)
    x.unitize()

    y = z.cross(x)
    return Frame(point, x, y)


class Toolpath:
    """A list of COMPAS Frames the robot can follow, plus the tile it belongs to.

    Every method that changes the geometry returns a NEW Toolpath and leaves
    the original alone. That means you can build variations without ever
    losing what the visitor actually drew.
    """

    def __init__(self, frames, tile_id=None, job_id=None):
        if not frames:
            raise ValueError("The toolpath contains no frames.")
        self.frames = frames
        self.tile_id = tile_id
        self.job_id = job_id

    # -- loading ----------------------------------------------------------

    @classmethod
    def from_json(cls, filepath):
        data = json_load(filepath)
        if "frames" not in data:
            raise KeyError("The JSON file does not contain 'frames'.")
        return cls(
            data["frames"],
            tile_id=data.get("tile_id"),
            job_id=data.get("job_id"),
        )

    def describe(self):
        print("Frames:  ", len(self.frames))
        print("Tile ID: ", self.tile_id)
        print("Job ID:  ", self.job_id)
        print("Length:  ", "{:.0f} mm".format(self.length))
        print("First:   ", self.frames[0].point)
        print("Last:    ", self.frames[-1].point)

    # -- basics -----------------------------------------------------------

    @property
    def first(self):
        return self.frames[0]

    @property
    def last(self):
        return self.frames[-1]

    @property
    def remaining(self):
        """Everything after the first frame. The robot moves to the first
        frame separately, then follows these."""
        return self.frames[1:]

    @property
    def length(self):
        """Total travel along the path, in mm."""
        total = 0.0
        for a, b in zip(self.frames, self.frames[1:]):
            total += a.point.distance_to_point(b.point)
        return total

    @property
    def is_long_enough(self):
        """False for stubs too short to be worth a full approach and retract."""
        return self.length >= MIN_FRAGMENT_MM

    def __len__(self):
        return len(self.frames)

    def _like_me(self, frames):
        """A new Toolpath carrying the same tile and job identity."""
        return Toolpath(frames, tile_id=self.tile_id, job_id=self.job_id)

    # -- pulling back from the surface ------------------------------------

    @staticmethod
    def safe_frame(frame, offset=None, toward=SPHERE_CENTER):
        """One frame, moved back from the net toward the centre of the
        structure. Same orientation, different position."""
        offset = config.SAFE_OFFSET if offset is None else offset
        direction = Vector.from_start_end(frame.point, toward)
        direction.unitize()
        return Frame(frame.point + direction * offset, frame.xaxis, frame.yaxis)

    def with_approach_and_retract(self, offset=None):
        """The path with a safe point added at each end, so the arm never
        drives straight at the net."""
        return self._like_me(
            [self.safe_frame(self.first, offset)]
            + self.frames
            + [self.safe_frame(self.last, offset)]
        )

    def with_standoff(self, offset=None, follow_surface=None):
        """The WHOLE path pulled back from the net. This is watering.

        Same line, same order — just sprayed from much further away, so the
        water arrives as mist rather than a jet.

        With follow_surface on, the distance is measured from the net at
        each point, so the whole path stays a constant distance from a
        curved surface. That matters at 700 mm: pulling straight back toward
        one centre point would leave the ends of a long path closer to the
        net than the middle.
        """
        offset = WATER_STANDOFF_MM if offset is None else offset
        follow_surface = LANES_FOLLOW_SURFACE if follow_surface is None else follow_surface

        if follow_surface:
            return self.on_surface(offset)
        return self._like_me([self.safe_frame(f, offset) for f in self.frames])

    # -- lanes ------------------------------------------------------------

    def translated(self, vector):
        """The whole path moved by a vector. Orientations are unchanged."""
        return self._like_me(
            [Frame(f.point + vector, f.xaxis, f.yaxis) for f in self.frames]
        )

    def on_surface(self, standoff=None, orient=None):
        """The path put back at a fixed distance from the net.

        For each frame: find the net underneath, then sit `standoff` mm off
        it along the surface normal. Frames that had drifted into or away
        from the surface end up where the nozzle should actually be.
        """
        from sybil import net as net_module

        the_net = net_module.net()
        standoff = self.standoff if standoff is None else standoff
        orient = LANES_ORIENT_TO_SURFACE if orient is None else orient

        placed = []
        for frame in self.frames:
            point = the_net.project(frame.point, standoff)
            if orient:
                normal = the_net.normal_at(point)
                placed.append(_frame_facing(point, normal, frame))
            else:
                placed.append(Frame(point, frame.xaxis, frame.yaxis))
        return self._like_me(placed)

    @property
    def standoff(self):
        """How far this path currently sits off the net, on average.

        Lanes copy this, so a stepped lane keeps whatever distance the
        original was projected at instead of inventing a new one.
        """
        from sybil import net as net_module

        the_net = net_module.net()
        distances = [the_net.distance(f.point) for f in self.frames]
        return sum(distances) / len(distances)

    def lanes(self, count=None, offset=None, direction=None, follow_surface=None):
        """The path copied several times, each stepped a little further down.

        Returns a list of Toolpaths, starting with the original. Spray them
        in order and the mark grows downward from the line the visitor drew.

        With follow_surface on (the default), each copy is stepped and then
        put back at the same distance from the net that the original had.
        The lane rides the curve instead of cutting through it, so collision
        is designed out rather than checked for afterwards.
        """
        count = LANE_COUNT if count is None else count
        offset = LANE_OFFSET_MM if offset is None else offset
        direction = LANE_DIRECTION if direction is None else direction
        follow_surface = LANES_FOLLOW_SURFACE if follow_surface is None else follow_surface

        step = direction.copy()
        step.unitize()

        if not follow_surface:
            return [self.translated(step * (offset * i)) for i in range(count)]

        # Measure once, so every lane keeps the original's distance from the
        # net rather than drifting a little further out with each step.
        standoff = self.standoff

        lanes = [self]
        for i in range(1, count):
            stepped = self.translated(step * (offset * i))
            lanes.append(stepped.on_surface(standoff))
        return lanes

    # -- orientation ------------------------------------------------------

    def with_fixed_orientation(self, orientation_frame):
        """Every frame locked to one orientation, taken from the robot's
        live pose at home. Avoids the wrist twisting along the path."""
        return self._like_me(
            [
                Frame(f.point, orientation_frame.xaxis, orientation_frame.yaxis)
                for f in self.frames
            ]
        )


# --------------------------------------------------------------------------
# Check: python sybil/toolpath.py
#
# Builds a fake path and exercises every method. No robot, no files.
# --------------------------------------------------------------------------

if __name__ == "__main__":
    from compas.geometry import Point

    frames = [Frame(Point(x, 1000, 900), [1, 0, 0], [0, 1, 0]) for x in range(0, 1600, 100)]
    path = Toolpath(frames, tile_id="03", job_id="test-001")

    print("--- original ---")
    path.describe()

    print("\n--- lanes ---")
    lanes = path.lanes()
    print("{} lanes, {:.0f} mm apart, direction {}".format(
        len(lanes), LANE_OFFSET_MM, list(LANE_DIRECTION)))
    for i, lane in enumerate(lanes):
        print("  lane {}  first point {}".format(i, lane.first.point))
    assert len(lanes) == LANE_COUNT
    assert lanes[0].first.point[2] == 900
    assert abs(lanes[1].first.point[2] - (900 - LANE_OFFSET_MM)) < 1e-6

    print("\n--- watering standoff ---")
    water = path.with_standoff()
    moved = path.first.point.distance_to_point(water.first.point)
    print("  path pulled back {:.0f} mm".format(moved))
    assert abs(moved - WATER_STANDOFF_MM) < 1e-6

    print("\n--- approach and retract ---")
    padded = path.with_approach_and_retract()
    print("  {} frames -> {} frames".format(len(path), len(padded)))
    assert len(padded) == len(path) + 2

    print("\n--- length filter ---")
    stub = Toolpath([frames[0], frames[1]])
    print("  full path {:.0f} mm, long enough: {}".format(path.length, path.is_long_enough))
    print("  stub      {:.0f} mm, long enough: {}".format(stub.length, stub.is_long_enough))
    assert path.is_long_enough and not stub.is_long_enough

    print("\n--- original untouched ---")
    assert path.first.point[2] == 900
    print("  yes, still at z=900")

    print("\ntoolpath ok")
