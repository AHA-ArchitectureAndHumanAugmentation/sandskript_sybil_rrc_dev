"""Shared compas_viewer display logic, used by the checkpoint scripts."""

import statistics
from pathlib import Path

from compas.colors import Color
from compas.datastructures import Mesh
from compas.geometry import Point, Polyline, Sphere, Vector
from compas_viewer import Viewer

from fixed_geometry import DEFAULT_WOBJ_ORIGIN, DEFAULT_WOBJ_XAXIS, DEFAULT_WOBJ_YAXIS

VIEW_MODE = "perspective"

AXIS_LENGTH_SCALE = 0.25      # X/Y (red/green) -- tiny, per-point orientation check
Z_AXIS_LENGTH_SCALE = 0.3     # Z (blue) -- the actual surface normal direction
SHOW_EVERY_NTH_FRAME = 1
SHOW_NORMALS = True           # set False to hide all X/Y/Z frame axes
SHOW_SURFACE = True           # set False to hide the spray surface mesh
SHOW_HOME = True              # set False to hide the home-position marker/axes
SHOW_WOBJ_AXES = True         # set False to hide the world object orientation axes

AXIS_LINEWIDTH = 0.8          # X/Y (red/green) line thickness
Z_AXIS_LINEWIDTH = 1          # Z (blue) line thickness
POLYLINE_BEFORE_WIDTH = 0.5
POLYLINE_AFTER_WIDTH = 1

TRAIL_POINT_SIZE = 8          # each point along the toolpath
START_POINT_SIZE = 10
END_POINT_SIZE = 10
ORIGIN_POINT_SIZE = 10
HOME_POINT_SIZE = 12

# Big reference axes (home, world object) are sized off framing_span, not
# point spacing -- they need to read clearly regardless of how tight the
# toolpath's own points are.
BIG_AXIS_SPAN_FRACTION = 0.12
BIG_AXIS_LINEWIDTH = 1.5

SURFACE_PATH = Path(__file__).resolve().parent / "sybil_geo" / "surface.obj"
SURFACE_OPACITY = 0.25

# Colors
COLOR_TARGET_SHELL = Color(0.70, 0.93, 0.93)    # light cyan -- inner/target sphere
COLOR_SAFETY_SHELL = Color(0.90, 0.98, 0.98)    # lightest cyan -- outer/safety sphere
COLOR_BEFORE = Color(0.88, 0.88, 0.86)          # soft warm grey
COLOR_AFTER = Color(0.15, 0.15, 0.18)           # near-charcoal
COLOR_START = Color(0.40, 0.78, 0.62)           # soft teal-green
COLOR_END = Color(0.85, 0.40, 0.40)             # soft coral-red
COLOR_ORIGIN = Color(0.95, 0.65, 0.25)          # warm amber -- robot / world object origin
COLOR_SURFACE = Color(0.75, 0.75, 0.78)         # neutral grey -- the physical spray surface
COLOR_HOME = Color(0.30, 0.55, 0.95)            # blue -- home TCP position


def _load_surface_mesh():
    if not SURFACE_PATH.is_file():
        return None
    return Mesh.from_obj(str(SURFACE_PATH))


def show_comparison(
    before_frames,
    after_frames,
    sphere_center=None,
    target_radius=None,
    safety_radius=None,
    show_every_nth_frame=SHOW_EVERY_NTH_FRAME,
    show_normals=SHOW_NORMALS,
    show_surface=SHOW_SURFACE,
    home_frame=None,
    show_home=SHOW_HOME,
    show_wobj_axes=SHOW_WOBJ_AXES,
):
    print(f"World origin (mm): ({DEFAULT_WOBJ_ORIGIN.x:.1f}, {DEFAULT_WOBJ_ORIGIN.y:.1f}, {DEFAULT_WOBJ_ORIGIN.z:.1f})")

    before_points = [f.point for f in before_frames]
    after_points = [f.point for f in after_frames]

    xs = [p.x for p in after_points]
    ys = [p.y for p in after_points]
    zs = [p.z for p in after_points]
    path_span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0)

    if len(after_points) > 1:
        gaps = [(after_points[i + 1] - after_points[i]).length for i in range(len(after_points) - 1)]
        spacing = statistics.median(gaps)
        print(f"Point spacing (mm) -- min: {min(gaps):.1f}  median: {spacing:.1f}  max: {max(gaps):.1f}")
    else:
        spacing = path_span

    axis_length = spacing * AXIS_LENGTH_SCALE
    z_axis_length = spacing * Z_AXIS_LENGTH_SCALE
    print(f"Path span (mm): {path_span:.1f}   axis length (mm): {axis_length:.1f}   z-axis length (mm): {z_axis_length:.1f}")

    surface_mesh = _load_surface_mesh() if show_surface else None
    if show_surface and surface_mesh is None:
        print(f"No surface mesh found at {SURFACE_PATH} -- skipping.")

    framing_xs, framing_ys, framing_zs = list(xs), list(ys), list(zs)

    framing_radius = safety_radius or target_radius
    if sphere_center is not None and framing_radius is not None:
        framing_xs += [sphere_center.x - framing_radius, sphere_center.x + framing_radius]
        framing_ys += [sphere_center.y - framing_radius, sphere_center.y + framing_radius]
        framing_zs += [sphere_center.z - framing_radius, sphere_center.z + framing_radius]

    if surface_mesh is not None:
        surface_points = [surface_mesh.vertex_coordinates(vkey) for vkey in surface_mesh.vertices()]
        framing_xs += [p[0] for p in surface_points]
        framing_ys += [p[1] for p in surface_points]
        framing_zs += [p[2] for p in surface_points]

    if show_home and home_frame is not None:
        framing_xs.append(home_frame.point.x)
        framing_ys.append(home_frame.point.y)
        framing_zs.append(home_frame.point.z)

    center = Point(
        (max(framing_xs) + min(framing_xs)) / 2,
        (max(framing_ys) + min(framing_ys)) / 2,
        (max(framing_zs) + min(framing_zs)) / 2,
    )
    framing_span = max(
        max(framing_xs) - min(framing_xs),
        max(framing_ys) - min(framing_ys),
        max(framing_zs) - min(framing_zs),
        1.0,
    )
    big_axis_length = framing_span * BIG_AXIS_SPAN_FRACTION

    viewer = Viewer(show_grid=False, viewmode=VIEW_MODE)

    ############## Camera Framing ##############
    camera = viewer.renderer.camera
    camera.target = [center.x, center.y, center.z]
    camera.position = [center.x - framing_span, center.y - framing_span, center.z + framing_span * 0.75]
    camera.near = framing_span * 0.001
    camera.far = framing_span * 10

    ############## Spray Surface ##############
    if surface_mesh is not None:
        viewer.scene.add(surface_mesh, facecolor=COLOR_SURFACE, opacity=SURFACE_OPACITY, name="spray surface")

    ############## Reference Shells ##############
    if sphere_center is not None and target_radius is not None:
        viewer.scene.add(
            Sphere(target_radius, point=sphere_center),
            facecolor=COLOR_TARGET_SHELL, opacity=0.35, name="target shell",
        )
    if sphere_center is not None and safety_radius is not None:
        viewer.scene.add(
            Sphere(safety_radius, point=sphere_center),
            facecolor=COLOR_SAFETY_SHELL, opacity=0.15, name="safety shell",
        )

    ############## Toolpath Polylines ##############
    viewer.scene.add(Polyline(before_points), linecolor=COLOR_BEFORE, linewidth=POLYLINE_BEFORE_WIDTH, show_points=False, name="original (before)")
    viewer.scene.add(Polyline(after_points), linecolor=COLOR_AFTER, linewidth=POLYLINE_AFTER_WIDTH, show_points=False, name="processed (after)")

    ############## Points and Frame Axes ##############
    for i, frame in enumerate(after_frames):
        viewer.scene.add(Point(*frame.point), pointcolor=Color(0.53, 0.53, 0.5), pointsize=TRAIL_POINT_SIZE, name=f"{i}: point")

        if not show_normals:
            continue
        if i % show_every_nth_frame != 0:
            continue

        point = frame.point
        viewer.scene.add(frame.xaxis.scaled(axis_length), anchor=point, linecolor=Color.red(), linewidth=AXIS_LINEWIDTH, name=f"{i}: x-axis")
        viewer.scene.add(frame.yaxis.scaled(axis_length), anchor=point, linecolor=Color.green(), linewidth=AXIS_LINEWIDTH, name=f"{i}: y-axis")
        viewer.scene.add(frame.zaxis.scaled(z_axis_length), anchor=point, linecolor=Color.blue(), linewidth=Z_AXIS_LINEWIDTH, name=f"{i}: z-axis (radial, toward center)")

    ############## World Object Orientation ##############
    # Shows the RAW DEFAULT_WOBJ_XAXIS/YAXIS constants as actually defined
    # in fixed_geometry.py -- never derived from home_frame or anything
    # else. If world object and home don't visually agree, that mismatch
    # IS the debugging signal; the preview must not paper over it.
    if show_wobj_axes:
        wobj_xaxis = Vector(*DEFAULT_WOBJ_XAXIS)
        wobj_xaxis.unitize()
        wobj_yaxis = Vector(*DEFAULT_WOBJ_YAXIS)
        wobj_yaxis.unitize()
        wobj_zaxis = Vector(*wobj_xaxis.cross(wobj_yaxis))

        viewer.scene.add(wobj_xaxis.scaled(big_axis_length), anchor=DEFAULT_WOBJ_ORIGIN, linecolor=Color.red(), linewidth=BIG_AXIS_LINEWIDTH, name="world object x-axis")
        viewer.scene.add(wobj_yaxis.scaled(big_axis_length), anchor=DEFAULT_WOBJ_ORIGIN, linecolor=Color.green(), linewidth=BIG_AXIS_LINEWIDTH, name="world object y-axis")
        viewer.scene.add(wobj_zaxis.scaled(big_axis_length), anchor=DEFAULT_WOBJ_ORIGIN, linecolor=Color.blue(), linewidth=BIG_AXIS_LINEWIDTH, name="world object z-axis")

    ############## Home Position (approximate -- see caveat at top) #########
    if show_home and home_frame is not None:
        viewer.scene.add(Point(*home_frame.point), pointcolor=COLOR_HOME, pointsize=HOME_POINT_SIZE, name="home position (approx., offline FK)")
        viewer.scene.add(home_frame.xaxis.scaled(big_axis_length), anchor=home_frame.point, linecolor=Color.red(), linewidth=BIG_AXIS_LINEWIDTH, name="home x-axis")
        viewer.scene.add(home_frame.yaxis.scaled(big_axis_length), anchor=home_frame.point, linecolor=Color.green(), linewidth=BIG_AXIS_LINEWIDTH, name="home y-axis")
        viewer.scene.add(home_frame.zaxis.scaled(big_axis_length), anchor=home_frame.point, linecolor=Color.blue(), linewidth=BIG_AXIS_LINEWIDTH, name="home z-axis")

    ############## Start / End / Origin ##############
    viewer.scene.add(Point(*after_points[0]), pointcolor=COLOR_START, pointsize=START_POINT_SIZE, name="start (safe frame)")
    viewer.scene.add(Point(*after_points[-1]), pointcolor=COLOR_END, pointsize=END_POINT_SIZE, name="end (safe frame)")
    viewer.scene.add(Point(*DEFAULT_WOBJ_ORIGIN), pointcolor=COLOR_ORIGIN, pointsize=ORIGIN_POINT_SIZE, name="world origin")

    viewer.show()