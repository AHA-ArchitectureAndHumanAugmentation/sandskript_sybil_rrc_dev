"""Shared compas_viewer display logic, used by the checkpoint scripts."""

from compas.colors import Color
from compas.geometry import Point, Polyline
from compas_viewer import Viewer

from robot_geometry import DEFAULT_WOBJ_ORIGIN

VIEW_MODE = "perspective"

# Tune these to make points/normals bigger or smaller.
POINT_SIZE = 14
NORMAL_LENGTH_FACTOR = 0.15   # fraction of the path's own bounding box


def show_comparison(before_frames, after_frames):
    before_points = [f.point for f in before_frames]
    after_points = [f.point for f in after_frames]

    xs = [p.x for p in after_points]
    ys = [p.y for p in after_points]
    zs = [p.z for p in after_points]
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0)
    normal_length = size * NORMAL_LENGTH_FACTOR
    print(f"Bounding box size (mm): X={max(xs)-min(xs):.1f}, Y={max(ys)-min(ys):.1f}, Z={max(zs)-min(zs):.1f}")

    viewer = Viewer(show_grid=False, viewmode=VIEW_MODE)

    viewer.scene.add(Polyline(before_points), linecolor=Color(0.85, 0.85, 0.85), show_points=False, name="original (before)")
    viewer.scene.add(Polyline(after_points), linecolor=Color(0.1, 0.1, 0.1), show_points=False, name="processed (after)")

    for i, frame in enumerate(after_frames):
        viewer.scene.add(Point(*frame.point), pointcolor=Color(0.53, 0.53, 0.5), pointsize=POINT_SIZE, name=f"{i}: point")
        normal_vector = frame.zaxis.scaled(normal_length)
        viewer.scene.add(normal_vector, anchor=frame.point, linecolor=Color(0.5, 0.0, 0.9), name=f"{i}: normal")

    viewer.scene.add(Point(*after_points[0]), pointcolor=Color(0.36, 0.79, 0.65), pointsize=20, name="start")
    viewer.scene.add(Point(*after_points[-1]), pointcolor=Color(0.89, 0.29, 0.29), pointsize=20, name="end")
    viewer.scene.add(Point(*DEFAULT_WOBJ_ORIGIN), pointcolor=Color(1.0, 0.6, 0.0), pointsize=20, name="world origin")

    viewer.show()