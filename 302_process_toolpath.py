#!/usr/bin/env python3
"""Process a converted toolpath into a robot-ready JSON file.

Usage: python 302_process_toolpath.py converted_toolpath/path_compas_1.json
"""

import sys
from pathlib import Path

from compas.data import json_dump, json_load
from compas.geometry import Frame, Vector

from robot_geometry import oriented_frame
from view_utils import show_frames

ROOT = Path(__file__).resolve().parent

TOOLPATH_OFFSET = Vector(-400.0, 0.0, 0.0)
SAFE_OFFSET = 200.0


def safe_frame(frame, offset=SAFE_OFFSET):
    return Frame(frame.point, frame.xaxis, frame.yaxis).translated(Vector(0, 0, offset))


def apply_sphere_orientation(frames):
    """Re-orient every frame to spray toward SPHERE_CENTER (robot_geometry.py).

    Uses each frame's existing xaxis as the path tangent. Not yet wired
    into the pipeline below -- turn this on once real sphere coordinates
    are set in robot_geometry.py.
    """
    return [oriented_frame(frame.point, frame.xaxis) for frame in frames]


infile = Path(sys.argv[1])
frames = json_load(infile)["frames"]
if not frames:
    raise ValueError("Empty 'frames' list.")

print("Showing input. Close the window to continue.")
show_frames(frames)

offset_frames = [f.translated(TOOLPATH_OFFSET) for f in frames]
processed = [safe_frame(offset_frames[0])] + offset_frames + [safe_frame(offset_frames[-1])]

outdir = ROOT / "processed_toolpath"
outdir.mkdir(exist_ok=True)
outfile = outdir / f"{infile.stem}_ready.json"
json_dump({"frames": processed}, outfile)

print(f"Saved {len(processed)} frames to {outfile}")

print("Showing processed output.")
show_frames(processed)