#!/usr/bin/env python3
"""Process a converted toolpath into a robot-ready JSON file.

Data flows: data/in -> data/compas -> data/processed -> (data/send_to_robot)

Usage: python 302_process_toolpath.py data/compas/some_file_compas.json
"""

import sys
from pathlib import Path

from compas.data import json_dump, json_load
from compas.geometry import Frame, Vector

from view_utils import show_comparison

ROOT = Path(__file__).resolve().parent

DEFAULT_INPUT_PATH = ROOT / "data" / "compas" / "path_compas.json"
INPUT_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT_PATH

# Strip "_compas" from the name if present, so the next stage's suffix
# reads cleanly: "<name>_compas.json" -> "<name>_processed.json",
# not "<name>_compas_processed.json".
BASE_NAME = INPUT_PATH.stem
if BASE_NAME.endswith("_compas"):
    BASE_NAME = BASE_NAME[: -len("_compas")]

TOOLPATH_OFFSET = Vector(0, 0, 400.0)
SAFE_OFFSET = 200.0


def safe_frame(frame, offset=SAFE_OFFSET):
    return Frame(frame.point, frame.xaxis, frame.yaxis).translated(Vector(0, 0, offset))


frames = json_load(INPUT_PATH)["frames"]
if not frames:
    raise ValueError("Empty 'frames' list.")

offset_frames = [f.translated(TOOLPATH_OFFSET) for f in frames]
processed = [safe_frame(offset_frames[0])] + offset_frames + [safe_frame(offset_frames[-1])]

outdir = ROOT / "data" / "processed"
outdir.mkdir(exist_ok=True)
outfile = outdir / f"{BASE_NAME}_processed.json"
json_dump({"frames": processed}, outfile)

print(f"Saved {len(processed)} frames to {outfile}")

show_comparison(frames, processed)