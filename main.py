#!/usr/bin/env python3
"""Runs the toolpath pipeline in order: convert -> process -> send to robot.

Edit INPUT_PATH below to select which file the whole pipeline runs on.

303 needs the robot connected via Docker/ROS to succeed -- it's expected to
error out for now, until that's set up.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Change this line to select which file goes through the whole pipeline.
INPUT_PATH = ROOT / "toolpath" / "2026-07-27_11-48-59" / "path.json"

CONVERTED_PATH = ROOT / "converted_toolpath" / f"{INPUT_PATH.stem}_compas.json"
PROCESSED_PATH = ROOT / "processed_toolpath" / f"{CONVERTED_PATH.stem}_ready.json"

print("=== 301: convert ===")
subprocess.run(["python", "301_convert_to_compas_json.py", str(INPUT_PATH)], check=True)

print("=== 302: process ===")
subprocess.run(["python", "302_process_toolpath.py", str(CONVERTED_PATH)], check=True)

print("=== 303: send to robot ===")
subprocess.run(["python", "303_send_to_robot.py"], check=True)