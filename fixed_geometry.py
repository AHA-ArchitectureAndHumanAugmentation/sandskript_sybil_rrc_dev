"""
FIXED GEOMETRY

NO TOUCHY. Hard, physical constants for the Sybil installation --
the single source of truth for anything tied to a real-world
measurement. Nothing else in the repo should redefine these; scripts
import from here instead (currently 301, 302, with 303's MQTT bridge
and 304's robot execution pulling in whatever they need as they're
built out).

Everything shares ONE origin: (0, 0, 0) is the robot's own base, is
the single world object's origin, and is the safety sphere's center --
the same literal point, referenced everywhere below, not retyped.
There is only one world object in this repo; nothing else should
define a second one.

SAFETY_RADIUS is the hard reach limit. No toolpath point, from any
script, at any stage, may ever end up farther than this from the
origin.
"""

from compas.geometry import Point

WORLD_ORIGIN = Point(0.0, 0.0, 0.0)

# The one world object -- same literal origin as WORLD_ORIGIN, not a
# separately-typed copy of the same numbers.
DEFAULT_WOBJ_ORIGIN = WORLD_ORIGIN
DEFAULT_WOBJ_XAXIS = [1000.0, 0.0, 0.0]
DEFAULT_WOBJ_YAXIS = [0.0, 1000.0, 0.0]

# The safety sphere -- centered on WORLD_ORIGIN, on purpose. Nothing
# the robot does may cross this boundary.
SPHERE_CENTER = WORLD_ORIGIN
SAFETY_RADIUS = 1600.0