#!/usr/bin/env python3
"""Runs the toolpath pipeline in order: convert -> process -> send to robot.

Data flows: data/in -> data/compas -> data/processed -> (data/send_to_robot)

Edit INPUT_PATH below to select which file goes through the whole pipeline.

303 is currently skipped -- it needs the robot connected via Docker/ROS,
and there's a known offset-doubling issue to resolve first (see the
KNOWN ISSUE comment in 303_send_to_robot.py).
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Change this line to select which file goes through the whole pipeline.
INPUT_PATH = ROOT / "data" / "in" / "2026-07-28_14-35-32" / "path.json"

BASE_NAME = INPUT_PATH.stem
if BASE_NAME == "path":
    BASE_NAME = INPUT_PATH.parent.name

CONVERTED_PATH = ROOT / "data" / "compas" / f"{BASE_NAME}_compas.json"
PROCESSED_PATH = ROOT / "data" / "processed" / f"{BASE_NAME}_processed.json"

print("=== 301: convert ===")
subprocess.run(["python", "301_convert_to_compas_json.py", str(INPUT_PATH)], check=True)

print("=== 302: process ===")
subprocess.run(["python", "302_process_toolpath.py", str(CONVERTED_PATH)], check=True)

# print("=== 303: send to robot ===")
# subprocess.run(["python", "303_send_to_robot.py", str(PROCESSED_PATH)], check=True)