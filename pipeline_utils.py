"""Shared utilities for the toolpath pipeline -- imported by main.py,
300_watch_and_run.py, 300b_zmq_listener.py, and 300b_test_publisher.py.

Numbered pipeline files (300_, 301_, etc.) can't be imported directly --
Python identifiers can't start with a digit -- so anything genuinely
shared has to live in an unnumbered module like this one instead.
"""

import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IN_DIR = ROOT / "data" / "in"

TIMESTAMP_FOLDER = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}")

SETTLE_TIME = 1.0  # seconds a file's size must stay unchanged before it's "done writing"


def latest_input_path():
    """Picks the folder whose NAME has the newest timestamp -- not the
    newest modified-time, which git operations can silently reset."""
    folders = [p for p in IN_DIR.iterdir() if p.is_dir() and TIMESTAMP_FOLDER.match(p.name)]
    if not folders:
        raise FileNotFoundError(f"No timestamped folders found in {IN_DIR}")
    latest_folder = max(folders, key=lambda p: p.name)
    return latest_folder / "path.json"


def is_file_stable(path, settle_time=SETTLE_TIME):
    """True once `path`'s size hasn't changed for `settle_time` seconds --
    avoids acting on a file that's still mid-write."""
    try:
        size_before = path.stat().st_size
    except FileNotFoundError:
        return False
    time.sleep(settle_time)
    try:
        size_after = path.stat().st_size
    except FileNotFoundError:
        return False
    return size_before == size_after


def describe_input(path):
    received_at = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "strokes" in data:
        stroke_count = len(data["strokes"])
        point_count = sum(len(stroke) for stroke in data["strokes"])
    elif "frames" in data:
        stroke_count = None
        point_count = len(data["frames"])
    else:
        stroke_count = point_count = None

    print("=== Received input ===")
    print(f"Folder:   {path.parent.name}")
    print(f"File:     {path}")
    print(f"Modified: {received_at}")
    if stroke_count is not None:
        print(f"Strokes:  {stroke_count}")
    if point_count is not None:
        print(f"Points:   {point_count}")
    print()


def run_pipeline(input_path):
    """Runs 301 -> 302 -> 304 on one capture. The ONE place this
    sequence is defined -- everything else calls this instead of
    reimplementing it, so they can't quietly diverge again."""
    base_name = input_path.stem
    if base_name == "path":
        base_name = input_path.parent.name

    converted_path = ROOT / "data" / "compas" / f"{base_name}_compas.json"
    processed_path = ROOT / "data" / "processed" / f"{base_name}_processed.json"

    print("=== 301: convert ===")
    subprocess.run(["python", "301_convert_to_compas_json.py", str(input_path)], check=True)

    print("=== 302: process ===")
    subprocess.run(["python", "302_process_toolpath.py", str(converted_path)], check=True)

    print("\n*** 304 runs next -- its MODE constant governs what actually happens. ***")
    print("=== 304: send to robot ===")
    subprocess.run(["python", "304_send_to_robot.py", str(processed_path)], check=True)

    print(f"=== Pipeline complete for {base_name} ===\n")