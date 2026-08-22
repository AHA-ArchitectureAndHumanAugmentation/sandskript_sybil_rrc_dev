"""
Sybil — the net surface.

WHAT THIS FILE IS FOR
Owns sybil_geo/surface.obj and answers questions about it:

    closest_point(p)        nearest point on the net
    normal_at(p)            which way the net faces there
    project(p, standoff)    a point sitting `standoff` mm off the net,
                            measured along the surface normal
    distance(p)             how far a point is from the net

WHY IT MATTERS
Lane stepping copies a path downward. On a flat wall that would be fine. On
a double-curved net, a straight-down copy drifts INTO the surface in some
places and away from it in others. So a lane is not just "the path, moved" —
it is "the path, moved, then put back at the right distance from whatever is
now underneath it".

That is what project() is for. Paths are generated with the surface in mind,
rather than generated blindly and checked afterwards.

Loading a large OBJ takes a moment, so the mesh is read once and kept, along
with a grid index that makes closest-point lookups fast enough to run on
every frame of every lane.

Lives in the RRC repo only:
    sandskript_sybil_rrc_dev/sybil/net.py
"""

from __future__ import annotations

import math

from compas.datastructures import Mesh
from compas.geometry import Point, Vector

from sybil import config


# ==========================================================================
# SETTINGS
# ==========================================================================

NET_MESH_PATH = config.REPO_ROOT / "sybil_geo" / "surface.obj"
# The whole net as one mesh. Everything is measured against this.
# If the physical net changes, re-export this file or every answer here is
# quietly wrong.

SPRAY_STANDOFF_MM = 200.0
# How far the nozzle sits from the net while spraying substrate.
# This is the distance lanes are placed at, so it directly sets how thick
# and how wide the sprayed line comes out.
# Smaller = tighter, denser line. Larger = softer, more spread out.

CLEARANCE_STOP_MM = 40.0
# Closer than this and a path is refused — the "would have hit the net"
# line. Nothing runs. Raise to be more cautious.

CLEARANCE_WARN_MM = 80.0
# Closer than this and the path runs, but prints a warning. The gap between
# WARN and STOP is your margin for error.

GRID_SIZE_MM = 100.0
# Internal. How the mesh is chopped up to make lookups fast. Smaller = more
# memory, faster lookups. Only worth touching if projection feels slow.

# ==========================================================================


class Net:
    """The net surface, loaded once."""

    def __init__(self, path=None):
        self.path = NET_MESH_PATH if path is None else path

        if not self.path.exists():
            raise FileNotFoundError(
                "Net mesh not found: {}\n"
                "Path generation and clearance checking both need it.".format(self.path)
            )

        self.mesh = Mesh.from_obj(self.path)

        # Sample points: every vertex, plus every face centre. Face centres
        # matter because on a coarse mesh a frame can sit close to the middle
        # of a big triangle while being far from all three of its corners.
        self._points = []
        self._normals = []

        for vertex in self.mesh.vertices():
            self._points.append(Point(*self.mesh.vertex_coordinates(vertex)))
            self._normals.append(Vector(*self.mesh.vertex_normal(vertex)))

        for face in self.mesh.faces():
            self._points.append(Point(*self.mesh.face_centroid(face)))
            self._normals.append(Vector(*self.mesh.face_normal(face)))

        self._build_index()

    def _build_index(self):
        """Buckets the sample points into a grid, so a lookup only compares
        against nearby points instead of all of them."""
        self._grid = {}
        for i, p in enumerate(self._points):
            self._grid.setdefault(self._cell(p), []).append(i)

    def _cell(self, point):
        return (
            int(math.floor(point[0] / GRID_SIZE_MM)),
            int(math.floor(point[1] / GRID_SIZE_MM)),
            int(math.floor(point[2] / GRID_SIZE_MM)),
        )

    def _nearby(self, point, rings=1):
        """Indices of sample points in the cells around this point.
        Widens the search until it finds something."""
        cx, cy, cz = self._cell(point)
        while rings < 40:
            found = []
            for i in range(cx - rings, cx + rings + 1):
                for j in range(cy - rings, cy + rings + 1):
                    for k in range(cz - rings, cz + rings + 1):
                        found.extend(self._grid.get((i, j, k), ()))
            if found:
                return found
            rings += 1
        return range(len(self._points))

    # -- questions --------------------------------------------------------

    def _nearest_index(self, point):
        candidates = self._nearby(point)
        best, best_d = None, float("inf")
        for i in candidates:
            d = point.distance_to_point(self._points[i])
            if d < best_d:
                best, best_d = i, d
        return best, best_d

    def closest_point(self, point):
        """The nearest point on the net."""
        i, _ = self._nearest_index(point)
        return self._points[i]

    def normal_at(self, point):
        """Which way the net faces nearest to this point. Unitised, and
        flipped to face outward — away from the centre of the structure."""
        i, _ = self._nearest_index(point)
        normal = self._normals[i].copy()
        normal.unitize()

        # Face outward. "Outward" is away from the structure's centre, which
        # is where the robot stands.
        outward = Vector.from_start_end(_CENTRE, self._points[i])
        if normal.dot(outward) < 0:
            normal.scale(-1.0)
        return normal

    def distance(self, point):
        """How far a point is from the net, in mm."""
        _, d = self._nearest_index(point)
        return d

    def project(self, point, standoff=None):
        """A point sitting `standoff` mm off the net, along the surface normal.

        This is the important one. Give it a point that has drifted into or
        away from the surface, and it puts it back where the nozzle should be.
        """
        standoff = SPRAY_STANDOFF_MM if standoff is None else standoff
        i, _ = self._nearest_index(point)
        surface_point = self._points[i]
        normal = self.normal_at(surface_point)
        return surface_point + normal * standoff

    def check_normals(self):
        """Are the mesh normals consistently wound?

        project() places a point at surface + normal * standoff. If some
        faces in the OBJ are flipped, those points land BEHIND the net
        instead of in front — silently, and only in patches.

        This compares each pair of faces that share an edge. On a correctly
        wound mesh, neighbours point in similar directions no matter what
        shape the net is overall. Comparing against a centre point would
        give false alarms on a net that wraps around, so neighbours are the
        reliable test.
        """
        opposed = 0
        checked = 0

        for u, v in self.mesh.edges():
            faces = self.mesh.edge_faces((u, v))
            a, b = faces[0], faces[1]
            if a is None or b is None:
                continue  # boundary edge, only one face
            na = Vector(*self.mesh.face_normal(a))
            nb = Vector(*self.mesh.face_normal(b))
            if na.length < 1e-9 or nb.length < 1e-9:
                continue
            na.unitize()
            nb.unitize()
            checked += 1
            if na.dot(nb) < 0:
                opposed += 1

        share = 100.0 * opposed / checked if checked else 0.0

        print("\nNormal check")
        print("  {} interior edges checked".format(checked))
        print("  {} have neighbours facing opposite ways ({:.1f}%)".format(opposed, share))
        if share < 1:
            print("  ok — consistent winding")
        elif share < 5:
            print("  mostly fine — a few flipped faces, worth a look in Rhino")
        else:
            print("  WARNING — mixed winding. project() will put some frames")
            print("  behind the net. Unify normals in Rhino and re-export.")
        return share

    def describe(self):
        print("Net: {}".format(self.path))
        print("  {} vertices, {} faces, {} sample points".format(
            self.mesh.number_of_vertices(),
            self.mesh.number_of_faces(),
            len(self._points)))
        xs = [p[0] for p in self._points]
        ys = [p[1] for p in self._points]
        zs = [p[2] for p in self._points]
        print("  x {:.0f} to {:.0f}".format(min(xs), max(xs)))
        print("  y {:.0f} to {:.0f}".format(min(ys), max(ys)))
        print("  z {:.0f} to {:.0f}".format(min(zs), max(zs)))


# The centre of the structure, used to work out which way is "outward".
# Imported lazily so this module can be read without fixed_geometry present.
try:
    from fixed_geometry import SPHERE_CENTER as _CENTRE
except ImportError:
    _CENTRE = Point(0, 0, 0)


# --------------------------------------------------------------------------
# One shared instance
# --------------------------------------------------------------------------

_net = None


def net():
    """The net, loaded on first use and kept afterwards."""
    global _net
    if _net is None:
        _net = Net()
    return _net


# --------------------------------------------------------------------------
# Clearance
# --------------------------------------------------------------------------

class ClearanceReport:
    """What a check found. Truthy when the path is safe to run."""

    def __init__(self, distances, label=""):
        self.distances = distances
        self.label = label

    @property
    def closest(self):
        return min(self.distances) if self.distances else float("inf")

    @property
    def furthest(self):
        return max(self.distances) if self.distances else 0.0

    @property
    def too_close(self):
        return [i for i, d in enumerate(self.distances) if d < CLEARANCE_STOP_MM]

    @property
    def warnings(self):
        return [i for i, d in enumerate(self.distances)
                if CLEARANCE_STOP_MM <= d < CLEARANCE_WARN_MM]

    @property
    def is_safe(self):
        return not self.too_close

    def __bool__(self):
        return self.is_safe

    def report(self):
        print("\nClearance — {}".format(self.label or "toolpath"))
        print("  {} frames, closest {:.0f} mm, furthest {:.0f} mm".format(
            len(self.distances), self.closest, self.furthest))

        if self.too_close:
            print("  REFUSED — {} frame(s) under {:.0f} mm".format(
                len(self.too_close), CLEARANCE_STOP_MM))
            for i in self.too_close[:5]:
                print("    frame {:<4} {:.0f} mm".format(i, self.distances[i]))
            if len(self.too_close) > 5:
                print("    ... and {} more".format(len(self.too_close) - 5))
        elif self.warnings:
            print("  WARNING — {} frame(s) under {:.0f} mm. Runs, but look at it.".format(
                len(self.warnings), CLEARANCE_WARN_MM))
        else:
            print("  ok")

        return self.is_safe


def check(toolpath, label=""):
    """Measures every frame of a toolpath against the net.

    Note this measures POSITIONS only. It does not know the shape of the
    tool, the wrist, or the arm behind it — so it catches a path that has
    drifted into the surface, not an elbow clipping a corner. Keep using
    the preview viewer as well.
    """
    surface = net()
    distances = [surface.distance(f.point) for f in toolpath.frames]
    return ClearanceReport(distances, label=label or str(toolpath.tile_id))


# --------------------------------------------------------------------------
# Check: python sybil/net.py
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import time

    surface = net()
    surface.describe()

    # Take a real point on the net and work outward from it.
    sample = surface._points[len(surface._points) // 2]
    normal = surface.normal_at(sample)
    print("\nSample point on the net: {}".format(sample))
    print("  normal there: {}".format([round(v, 3) for v in normal]))

    at_spray = surface.project(sample)
    print("\nProjected to spray standoff:")
    print("  {:.0f} mm from the net (asked for {:.0f})".format(
        surface.distance(at_spray), SPRAY_STANDOFF_MM))

    at_water = surface.project(sample, 700.0)
    print("\nProjected to watering standoff:")
    print("  {:.0f} mm from the net (asked for 700)".format(surface.distance(at_water)))

    # A point that has drifted 50 mm INTO the surface gets pushed back out.
    inside = Point(*(sample - normal * 50.0))
    fixed = surface.project(inside)
    print("\nA point 50 mm inside the net:")
    print("  before {:.0f} mm away, after {:.0f} mm away".format(
        surface.distance(inside), surface.distance(fixed)))

    surface.check_normals()

    started = time.time()
    for _ in range(200):
        surface.project(sample)
    elapsed = time.time() - started
    print("\n200 projections in {:.2f} s ({:.1f} ms each)".format(
        elapsed, elapsed / 200 * 1000))

    print("\nnet ok")