"""Shared compas_viewer display logic, used by the checkpoint scripts."""

from compas.colors import Color
from compas.geometry import Line, Point, Polyline
from compas_viewer import Viewer


def show_frames(frames):
    points = [f.point for f in frames]

    xs = [p.x for p in points]
    ys = [p.y for p in points]
    zs = [p.z for p in points]
    bbox_label = f"X={max(xs)-min(xs):.1f}, Y={max(ys)-min(ys):.1f}, Z={max(zs)-min(zs):.1f}"
    print(f"Bounding box size (mm): {bbox_label}")

    viewer = Viewer(show_grid=False)

    # Fixed 1000mm reference line -- always this real length, no matter
    # what the data is. If the path looks tiny next to this, or dwarfs
    # it completely, the scale conversion is very likely wrong.
    reference = Line([0, 0, 0], [1000, 0, 0])
    viewer.scene.add(reference, linecolor=Color(1.0, 0.0, 1.0), linewidth=4, name="1000mm reference line")

    viewer.scene.add(
        Polyline(points),
        linecolor=Color(0.27, 0.27, 0.25),
        show_points=True,
        name=f"path (bbox mm: {bbox_label})",
    )
    viewer.scene.add(Point(*points[0]), pointcolor=Color(0.36, 0.79, 0.65), pointsize=16)
    viewer.scene.add(Point(*points[-1]), pointcolor=Color(0.89, 0.29, 0.29), pointsize=16)

    for frame in frames:
        viewer.scene.add(frame)  # shows this frame's orientation as an axes glyph

    viewer.show()