#!/usr/bin/env python3
"""
304_visualize_toolpath.py

Visualize a COMPAS toolpath JSON file in 3D using compas_viewer, at
different pipeline stages:

    raw     Frames exactly as stored in the JSON file.
    offset  After applying TOOLPATH_OFFSET (same translation 302_send_to_robot.py
            applies before sending anything to the robot).
    full    offset + the safe approach/retract frames (+SAFE_OFFSET in Z),
            i.e. what the robot actually does at the start and end of a run.

Opens compas_viewer's interactive window: drag to orbit, scroll to zoom,
and use the View menu for preset top/front/right angles. To save an
image, use View > Capture from the viewer's own menu.

Usage:
    python 304_visualize_toolpath.py data/toolpath_circle.json
    python 304_visualize_toolpath.py data/toolpath_line.json --stage raw
    python 304_visualize_toolpath.py converted_toolpath/path_compas_1.json --stage offset
    python 304_visualize_toolpath.py data/toolpath_circle.json --orientation
"""

from __future__ import annotations

import argparse
from pathlib import Path

from compas.colors import Color
from compas.data import json_load
from compas.geometry import Frame, Point, Polyline, Vector
from compas_viewer import Viewer

# The folder containing this file is treated as the project root,
# matching the convention used in 303_convert_to_compas_json.py.
PROJECT_ROOT = Path(__file__).resolve().parent

# Keep these in sync with 302_send_to_robot.py -- this script does not
# import that file directly, since running it does not require Docker,
# ROS, or a robot connection to be available.
TOOLPATH_OFFSET = Vector(-400.0, 0.0, 0.0)
SAFE_OFFSET = 200.0

STAGES = ("raw", "offset", "full")

START_COLOR = Color(0.36, 0.79, 0.65)
END_COLOR = Color(0.89, 0.29, 0.29)
PATH_COLOR = Color(0.27, 0.27, 0.25)
POINT_COLOR = Color(0.53, 0.53, 0.5)


def load_frames(filepath: Path) -> list[Frame]:
    data = json_load(filepath)
    if "frames" not in data:
        raise KeyError(f"{filepath} does not contain a 'frames' list.")
    frames = data["frames"]
    if not frames:
        raise ValueError(f"{filepath} contains an empty 'frames' list.")
    return frames


def get_safe_frame(frame: Frame, offset: float = SAFE_OFFSET) -> Frame:
    safe_frame = Frame(frame.point, frame.xaxis, frame.yaxis)
    return safe_frame.translated(Vector(0, 0, offset))


def build_stage(frames: list[Frame], stage: str) -> list[Frame]:
    if stage == "raw":
        return frames

    offset_frames = [frame.translated(TOOLPATH_OFFSET) for frame in frames]
    if stage == "offset":
        return offset_frames

    # "full": add safe approach/retract frames at start and end,
    # matching STEP 3 and the final retract move in 302_send_to_robot.py.
    first_safe = get_safe_frame(offset_frames[0])
    last_safe = get_safe_frame(offset_frames[-1])
    return [first_safe] + offset_frames + [last_safe]


def show_frames(frames: list[Frame], title: str, show_orientation: bool):
    viewer = Viewer()

    points = [frame.point for frame in frames]
    path = Polyline(points)
    viewer.scene.add(
        path,
        name=title,
        linecolor=PATH_COLOR,
        linewidth=2,
        show_points=True,
        pointcolor=POINT_COLOR,
        pointsize=8,
    )

    viewer.scene.add(Point(*points[0]), name="start", pointcolor=START_COLOR, pointsize=16)
    viewer.scene.add(Point(*points[-1]), name="end", pointcolor=END_COLOR, pointsize=16)

    if show_orientation:
        # Reference only -- 302_send_to_robot.py overrides every frame's
        # orientation with the TCP orientation captured at HOME_CONFIG.
        # See README.md section 7 ("Fixed Nozzle Orientation").
        for i, frame in enumerate(frames):
            viewer.scene.add(frame, name=f"frame_{i}")

    viewer.show()


def main():
    parser = argparse.ArgumentParser(description="Visualize a toolpath JSON file in 3D with compas_viewer.")
    parser.add_argument(
        "file", type=str,
        help="Path to a toolpath JSON file (relative to the repo root, or absolute).",
    )
    parser.add_argument(
        "--stage", choices=STAGES, default="full",
        help="Which pipeline stage to visualize (default: full).",
    )
    parser.add_argument(
        "--orientation", action="store_true",
        help="Draw each frame with its full axes glyph. Reference only -- see README section 7.",
    )
    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.is_absolute():
        filepath = PROJECT_ROOT / filepath
    if not filepath.is_file():
        raise FileNotFoundError(f"Could not find toolpath file: {filepath}")

    frames = load_frames(filepath)
    staged_frames = build_stage(frames, args.stage)

    title = f"{filepath.name} -- stage: {args.stage} ({len(staged_frames)} frames)"
    show_frames(staged_frames, title, args.orientation)


if __name__ == "__main__":
    main()