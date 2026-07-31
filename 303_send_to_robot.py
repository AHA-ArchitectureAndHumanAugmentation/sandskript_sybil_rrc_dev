from pathlib import Path
import sys

import compas_rrc as rrc
from compas.data import json_load
from compas.geometry import Frame, Vector

############## Constants ##############

HOME_CONFIG = [90.0, 15.0, -150.0, -5.0, -40.0, -215.0]
TOOL_NAME = "t_SprayingTool"
WORK_OBJECT = "wobj_SprayingNet"

SPRAY_OUTPUT = "ABB_Scalable_IO_0_DO1"
PUMP_OUTPUT = "ABB_Scalable_IO_0_DO2"

HOME_SPEED = 300
APPROACH_SPEED = 200
TOOLPATH_SPEED = 600

SAFE_OFFSET = 200.0
TOOLPATH_OFFSET = Vector(-400.0, 0.0, 0.0)

# KNOWN ISSUE: 302_process_toolpath.py already applies TOOLPATH_OFFSET and
# adds safe approach/retract frames before saving to data/processed/. If
# this script's input is a data/processed/ file, applying TOOLPATH_OFFSET
# again below will double-shift the path, and get_safe_frame() will add a
# second, redundant pair of safe frames. This needs to be resolved before
# actually running this script against a data/processed/ file for real --
# either remove the offset/safe-frame logic here (302 already did it), or
# point this script at data/compas/ instead of data/processed/.

# 0 = Communication only
# 1 = Read current robot position
# 2 = Move to HOME_CONFIG
# 3 = Move to safe frame
# 4 = Move to first toolpath frame
# 5 = Follow complete toolpath
TEST_STEP = 5

############## Functions ##############

def get_safe_frame(frame, offset=SAFE_OFFSET):
    safe_frame = Frame(frame.point, frame.xaxis, frame.yaxis)
    return safe_frame.translated(Vector(0, 0, offset))

def load_toolpath(filename):
    data = json_load(filename)
    if "frames" not in data:
        raise KeyError("The JSON file does not contain 'frames'.")
    return data["frames"]

def check_toolpath(frames):
    if not frames:
        raise ValueError("The toolpath contains no frames.")
    print("Number of toolpath frames:", len(frames))
    print("First toolpath frame:", frames[0])
    print("Last toolpath frame:", frames[-1])

def move_to_frame(abb, frame, speed, description):
    print("\nMoving to", description)
    print(frame)
    abb.send_and_wait(rrc.MoveToFrame(frame, speed=speed, zone=rrc.Zone.FINE))
    print(description, "completed.")

def