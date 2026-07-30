"""
ROBOT GEOMETRY CONFIGURATOR

Here we define where geometry is located (^-^)

Change SPHERE_CENTER, SPHERE_RADIUS, STANDOFF_DISTANCE here. Nothing
else in the repo should redefine these.

SPHERE_CENTER and SPHERE_RADIUS come from a sphere that sits behind S.GA
(Sybil's Garden Area), a little offset from the robot's own centre.

STANDOFF_DISTANCE is the distance the nozzle is pulled toward
SPHERE_CENTER, off the S.GA surface, so it clears the garden surface and
can spray without collision.

Path points already sit at their real, bent position on the garden
surface. That projection is handled upstream, in Lin's repo:
https://github.com/AHA-ArchitectureAndHumanAugmentation/SANDSKRIPT_depth-cam-to-robot

This module only points the nozzle away from SPHERE_CENTER, towards S.GA.

The robot's own base position is separate geometry, not defined here yet.
It will matter later for reach and collision checks, once we build those.
"""

from compas.geometry import Frame, Point, Vector, cross_vectors

# TODO: replace with real values measured in Rhino (mm, robot world coords)

SPHERE_CENTER = Point(0.0, 0.0, 0.0)   # sits behind S.GA, offset from robot centre
SPHERE_RADIUS = 1000.0            # centre to S.GA surface
STANDOFF_DISTANCE = 100.0         # nozzle clearance, measured from S.GA

# World / work-object reference frame, used when converting raw drawing
# data into COMPAS geometry.
DEFAULT_WOBJ_ORIGIN = [0.0, 0.0, 0.0]
DEFAULT_WOBJ_XAXIS = [1000.0, 0.0, 0.0]
DEFAULT_WOBJ_YAXIS = [0.0, 1000.0, 0.0]




def spray_direction(point):
    """Direction the nozzle sprays. Away from centre, outward through the point."""
    return Vector.from_start_end(SPHERE_CENTER, point).unitized()


def nozzle_position(point):
    """Where the nozzle sits. The point, pulled toward centre, off S.GA."""
    toward_center = Vector.from_start_end(point, SPHERE_CENTER).unitized()
    return point.translated(toward_center.scaled(STANDOFF_DISTANCE))


def oriented_frame(point, tangent):
    """Frame at point, oriented to spray outward through the point."""
    zaxis = spray_direction(point)
    yaxis = Vector(*cross_vectors(zaxis, tangent)).unitized()
    return Frame(nozzle_position(point), tangent, yaxis)