#!/usr/bin/env python3
"""Runs the toolpath pipeline in order: convert -> process -> send to robot.

Data flows: data/in -> data/compas -> data/processed -> (robot)

Edit INPUT_PATH below to select which file goes through the whole pipeline,
or leave it as the default to auto-pick the most recently exported curve.

304 always runs as the last step. Its own MODE constant, at the top of
304_send_to_robot.py, controls what actually happens:
    MODE = "preview" (default) -- shows the toolpath in compas_viewer,
                                    no robot/ROS connection attempted.
    MODE = "execute"           -- connects to ROS/ABB and runs TEST_STEP.
Edit MODE directly in 304_send_to_robot.py when ready to run against the
real robot -- deliberately not a flag here, so a robot move never gets
triggered as a side effect of just running this pipeline end to end.
"""

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IN_DIR = ROOT / "data" / "in"


def latest_input_path():
    folders = [p for p in IN_DIR.iterdir() if p.is_dir()]
    if not folders:
        raise FileNotFoundError(f"No folders found in {IN_DIR}")
    latest_folder = max(folders, key=lambda p: p.stat().st_mtime)
    return latest_folder / "path.json"


INPUT_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_input_path()

BASE_NAME = INPUT_PATH.stem
if BASE_NAME == "path":
    BASE_NAME = INPUT_PATH.parent.name

CONVERTED_PATH = ROOT / "data" / "compas" / f"{BASE_NAME}_compas.json"
PROCESSED_PATH = ROOT / "data" / "processed" / f"{BASE_NAME}_processed.json"

print(f"Using input: {INPUT_PATH}")

print("=== 301: convert ===")
subprocess.run(["python", "301_convert_to_compas_json.py", str(INPUT_PATH)], check=True)

print("=== 302: process ===")
subprocess.run(["python", "302_process_toolpath.py", str(CONVERTED_PATH)], check=True)

print("=== 304: send to robot ===")
subprocess.run(["python", "304_send_to_robot.py", str(PROCESSED_PATH)], check=True)