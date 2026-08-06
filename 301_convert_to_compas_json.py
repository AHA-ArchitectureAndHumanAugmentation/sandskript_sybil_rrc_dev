#!/usr/bin/env python3
"""
Convert a raw drawing toolpath JSON into a COMPAS geometry JSON file.
If the file is already converted, it's just shown as-is, no conversion.

Data flows: data/in -> data/compas -> data/processed -> (data/send_to_robot)

Usage:
    python 301_convert_to_compas_json.py
    python 301_convert_to_compas_json.py data/in/some_folder/path.json
"""

from __future__ import annotations

import json
import math
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable

from compas.data import json_load
from compas.geometry import Frame

from robot_geometry import DEFAULT_WOBJ_ORIGIN, DEFAULT_WOBJ_XAXIS, DEFAULT_WOBJ_YAXIS
from view_utils import show_comparison

PROJECT_ROOT = Path(__file__).resolve().parent

DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "in" / "path.json"
INPUT_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT_PATH

# If the filename itself is generic ("path.json", used by every capture),
# fall back to the parent folder's name -- that's where the real
# uniqueness lives, e.g. "2026-07-27_11-50-11".
BASE_NAME = INPUT_PATH.stem
if BASE_NAME == "path":
    BASE_NAME = INPUT_PATH.parent.name

OUTPUT_DIR = PROJECT_ROOT / "data" / "compas"
OUTPUT_PATH = OUTPUT_DIR / f"{BASE_NAME}_compas.json"

# COORDINATE_SCALE = 1000.0   # metres -> millimetres (current test data)
COORDINATE_SCALE = 1.0    # uncomment this line (and comment the one above) 


def new_guid() -> str:
    return str(uuid.uuid4())


def scaled_vector(values: Iterable[Any], scale: float = 1.0) -> list[float]:
    result = [float(value) * scale for value in values]
    if len(result) != 3:
        raise ValueError(f"Expected a 3D vector, received: {result!r}")
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"Vector contains a non-finite value: {result!r}")
    return [0.0 if abs(value) < 1e-12 else value for value in result]


def make_compas_frame(point: Iterable[Any], xaxis: Iterable[Any], yaxis: Iterable[Any]) -> dict[str, Any]:
    return {
        "dtype": "compas.geometry/Frame",
        "data": {
            "point": scaled_vector(point, COORDINATE_SCALE),
            "xaxis": scaled_vector(xaxis),
            "yaxis": scaled_vector(yaxis),
        },
        "guid": new_guid(),
    }


def make_compas_point(point: Iterable[Any]) -> dict[str, Any]:
    return {
        "dtype": "compas.geometry/Point",
        "data": scaled_vector(point),
        "guid": new_guid(),
    }


def extract_strokes(source: dict[str, Any]) -> list[list[dict[str, Any]]]:
    stroke_frames: list[list[dict[str, Any]]] = []
    for stroke_index, stroke in enumerate(source["strokes"]):
        if not isinstance(stroke, list):
            raise ValueError(f"Stroke {stroke_index} is not a list.")
        frames: list[dict[str, Any]] = []
        for point_index, item in enumerate(stroke):
            try:
                plane = item["plane"]
                origin = plane["origin"]
                xaxis = plane["xaxis"]
                yaxis = plane["yaxis"]
            except (KeyError, TypeError) as error:
                raise ValueError(
                    f"Missing plane information at stroke {stroke_index}, point {point_index}."
                ) from error
            frames.append(make_compas_frame(point=origin, xaxis=xaxis, yaxis=yaxis))
        stroke_frames.append(frames)
    return stroke_frames


def convert_to_compas(source: dict[str, Any]) -> dict[str, Any]:
    stroke_frames = extract_strokes(source)
    flat_frames = [frame for stroke in stroke_frames for frame in stroke]
    return {
        "strokes": stroke_frames,
        "frames": flat_frames,
        "wobj_origin": make_compas_point(DEFAULT_WOBJ_ORIGIN),
        "wobj_xaxis": make_compas_point(DEFAULT_WOBJ_XAXIS),
        "wobj_yaxis": make_compas_point(DEFAULT_WOBJ_YAXIS),
    }


if not INPUT_PATH.is_file():
    raise FileNotFoundError(f"Could not find the input toolpath:\n{INPUT_PATH}")

with INPUT_PATH.open("r", encoding="utf-8") as input_file:
    source = json.load(input_file)

if "strokes" in source:
    raw_frames = [
        Frame(item["plane"]["origin"], item["plane"]["xaxis"], item["plane"]["yaxis"])
        for stroke in source["strokes"]
        for item in stroke
    ]

    converted = convert_to_compas(source)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        json.dump(converted, output_file, indent=4, ensure_ascii=False)
        output_file.write("\n")

    print(f"Input:  {INPUT_PATH}")
    print(f"Output: {OUTPUT_PATH}")
    print(f"Strokes converted: {len(converted['strokes'])}")
    print(f"Frames converted: {len(converted['frames'])}")

    converted_frames = json_load(OUTPUT_PATH)["frames"]
    show_comparison(raw_frames, converted_frames)

else:
    frames = [Frame(f["data"]["point"], f["data"]["xaxis"], f["data"]["yaxis"]) for f in source["frames"]]
    print("Already in frames format. No conversion needed.")
    print(f"Input: {INPUT_PATH}")
    print(f"Frames: {len(frames)}")
    show_comparison(frames, frames)