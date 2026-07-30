#!/usr/bin/env python3
"""Process a converted toolpath into a robot-ready JSON file.

Just press Run -- edit INPUT_PATH below to test a different file.
"""

from pathlib import Path

from compas.data import json_dump, json_load
from compas.geometry import Frame, Vector

from view_utils import show_comparison

ROOT = Path(__file__).resolve().parent

import sys
INPUT_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "converted_toolpath" / "toolpath_circle_compas.json"

TOOLPATH_OFFSET = Vector(0, 0, 400.0)
SAFE_OFFSET = 200.0


def safe_frame(frame, offset=SAFE_OFFSET):
    return Frame(frame.point, frame.xaxis, frame.yaxis).translated(Vector(0, 0, offset))


frames = json_load(INPUT_PATH)["frames"]
if not frames:
    raise ValueError("Empty 'frames' list.")

offset_frames = [f.translated(TOOLPATH_OFFSET) for f in frames]
processed = [safe_frame(offset_frames[0])] + offset_frames + [safe_frame(offset_frames[-1])]

outdir = ROOT / "processed_toolpath"
outdir.mkdir(exist_ok=True)
outfile = outdir / f"{INPUT_PATH.stem}_ready.json"
json_dump({"frames": processed}, outfile)

print(f"Saved {len(processed)} frames to {outfile}")

show_comparison(frames, processed)
