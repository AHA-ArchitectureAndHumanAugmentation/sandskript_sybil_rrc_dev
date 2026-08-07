"""
304_send_to_robot.py

Sends a processed toolpath (list of COMPAS Frames) to the ABB GoFa 10 via
compas_rrc. Frames arriving here are already final -- offsetting, tweening,
etc. all happen upstream in 302_process_toolpath.py.
"""

from pathlib import Path
import sys

import compas_rrc as rrc
from compas.data import json_load
from compas.geometry import Frame, Vector

from fixed_geometry import SPHERE_CENTER, SAFETY_RADIUS
from view_utils import show_comparison

############## Mode ##############
# "preview" -- shows the toolpath in compas_viewer only. NO robot
#              connection is attempted at all.
# "execute" -- connects to ROS/ABB and runs the staged TEST_STEP below.
MODE = "preview"

# "fixed"  -- lock every frame's orientation to the one measured live at
#             HOME_CONFIG (Ruth's original behavior). All spray points
#             share one identical orientation.
# "radial" -- keep each frame's own per-point orientation from the tween
#             (302's output) -- each frame points radially, away from
#             SPHERE_CENTER, toward the material.
ORIENTATION_MODE = "radial"

############## Constants ##############

HOME_CONFIG = [90.0, 15.0, -150.0, -5.0, -40.0, -215.0]
TOOL_NAME = "t_SprayingTool"
WORK_OBJECT = "wobj_SprayingNet"

SPRAY_OUTPUT = "ABB_Scalable_IO_0_DO1"
PUMP_OUTPUT = "ABB_Scalable_IO_0_DO2"

HOME_SPEED = 300
APPROACH_SPEED = 200
TOOLPATH_SPEED = 600

SAFE_OFFSET = 100.0        # 10cm retreat, toward SPHERE_CENTER (not world Z)
PUMP_START_DELAY = 2.0

PROCESSED_DIR = Path(__file__).resolve().parent / "data" / "processed"

# Only used when MODE = "execute":
# 0 = Communication only
# 1 = Read current robot position
# 2 = Move to HOME_CONFIG
# 3 = Move to safe frame
# 4 = Move to first toolpath frame
# 5 = Follow complete toolpath
TEST_STEP = 5


def latest_processed_path():
    files = sorted(PROCESSED_DIR.glob("*_processed.json"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No processed files found in {PROCESSED_DIR}")
    return files[-1]


############## Toolpath ##############

class Toolpath:
    """Loads and validates a list of COMPAS Frames from JSON."""

    def __init__(self, frames):
        if not frames:
            raise ValueError("The toolpath contains no frames.")
        self.frames = frames

    @classmethod
    def from_json(cls, filepath):
        data = json_load(filepath)
        if "frames" not in data:
            raise KeyError("The JSON file does not contain 'frames'.")
        return cls(data["frames"])

    def check(self):
        print("Number of toolpath frames:", len(self.frames))
        print("First toolpath frame:", self.frames[0])
        print("Last toolpath frame:", self.frames[-1])

    def with_fixed_orientation(self, orientation_frame):
        """Keeps positions, replaces every frame's orientation with
        orientation_frame's axes -- locks the nozzle to a fixed direction."""
        fixed = [
            Frame(point=frame.point, xaxis=orientation_frame.xaxis, yaxis=orientation_frame.yaxis)
            for frame in self.frames
        ]
        return Toolpath(fixed)

    @staticmethod
    def safe_frame(frame, offset=SAFE_OFFSET, toward=SPHERE_CENTER):
        """A frame at `frame`'s position, retracted `offset` mm toward
        `toward` (SPHERE_CENTER by default) -- i.e. straight back off
        the material, along the real line to center, not a fixed world
        direction. Computed from POSITION alone, not from frame.zaxis --
        this stays correct regardless of which ORIENTATION_MODE is active."""
        direction = Vector.from_start_end(frame.point, toward)
        direction.unitize()
        safe_point = frame.point + direction * offset
        return Frame(safe_point, frame.xaxis, frame.yaxis)

    def with_approach_and_retract(self, offset=SAFE_OFFSET):
        """Returns a NEW Toolpath with a retracted approach frame prepended
        and a retracted retract frame appended -- for PREVIEW display only."""
        safe_first = self.safe_frame(self.first, offset)
        safe_last = self.safe_frame(self.last, offset)
        return Toolpath([safe_first] + self.frames + [safe_last])

    @property
    def first(self):
        return self.frames[0]

    @property
    def last(self):
        return self.frames[-1]

    @property
    def remaining(self):
        return self.frames[1:]

    def __len__(self):
        return len(self.frames)


############## Robot Session ##############

class RobotSession:
    """Owns the ROS/ABB connection plus low-level move/IO commands."""

    def __init__(self):
        self.ros = None
        self.abb = None

    def __enter__(self):
        print("\nConnecting to ROS...")
        self.ros = rrc.RosClient()
        self.ros.run()
        self.abb = rrc.AbbClient(self.ros, "/rob1")
        print("Connected to ROS.")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.ros is not None:
            try:
                if self.ros.is_connected:
                    self.ros.close()
            except Exception as close_error:
                print("Could not close ROS:", close_error)
        return False

    def prepare(self):
        self.abb.send_and_wait(rrc.SetTool(TOOL_NAME))
        self.abb.send_and_wait(rrc.SetWorkObject(WORK_OBJECT))
        self.abb.send_and_wait(rrc.SetAcceleration(20, 20))

    def move_to_frame(self, frame, speed, description):
        print("\nMoving to", description)
        print(frame)
        self.abb.send_and_wait(rrc.MoveToFrame(frame, speed=speed, zone=rrc.Zone.FINE))
        print(description, "completed.")

    def move_to_home(self):
        self.abb.send_and_wait(rrc.PrintText("Moving to home configuration"))
        self.abb.send_and_wait(rrc.MoveToJoints(HOME_CONFIG, [], speed=HOME_SPEED, zone=rrc.Zone.FINE))

    def get_joints(self):
        return self.abb.send_and_wait(rrc.GetJoints())

    def get_frame(self):
        return self.abb.send_and_wait(rrc.GetFrame())

    def pump_on(self):
        print("\nTurning pump ON.", flush=True)
        self.abb.send_and_wait(rrc.SetDigital(PUMP_OUTPUT, 1))
        print("Pump is ON.", flush=True)

    def pump_off(self):
        print("\nTurning pump OFF.", flush=True)
        self.abb.send_and_wait(rrc.SetDigital(PUMP_OUTPUT, 0))
        print("Pump is OFF.", flush=True)

    def spray_on(self):
        print("\nTurning spray valve ON.", flush=True)
        self.abb.send_and_wait(rrc.SetDigital(SPRAY_OUTPUT, 1))
        print("Spray valve is ON.", flush=True)

    def spray_off(self):
        print("\nTurning spray valve OFF.", flush=True)
        self.abb.send_and_wait(rrc.SetDigital(SPRAY_OUTPUT, 0))
        print("Spray valve is OFF.", flush=True)


############## Toolpath Executor ##############

class ToolpathExecutor:
    """Steps through TEST_STEP 0-5 in order, stopping at the requested step."""

    def __init__(self, robot, toolpath):
        self.robot = robot
        self.toolpath = toolpath

    def run(self, test_step):
        if test_step not in range(6):
            raise ValueError("test_step must be between 0 and 5.")

        print("\nSelected TEST_STEP:", test_step)

        self.step_0_communication()
        if test_step == 0:
            return

        self.step_1_read_position()
        if test_step == 1:
            return

        self.robot.prepare()

        self.step_2_move_home()
        if test_step == 2:
            return

        self.step_3_move_safe()
        if test_step == 3:
            return

        self.step_4_move_first()
        if test_step == 4:
            return

        self.step_5_follow_toolpath()

    def step_0_communication(self):
        self.robot.abb.send_and_wait(rrc.PrintText("Python connected to ABB"))
        print("STEP 0 completed: ABB communication works.")

    def step_1_read_position(self):
        joints, external_axes = self.robot.get_joints()
        print("\nCurrent robot joints:", joints)
        print("Current external axes:", external_axes)
        print("STEP 1 completed: Robot position received.")

    def step_2_move_home(self):
        self.robot.move_to_home()
        print("STEP 2 completed: Robot moved to HOME_CONFIG.")

        home_frame = self.robot.get_frame()
        print("\nHome TCP frame:", home_frame)
        print("Home nozzle X-axis:", home_frame.xaxis)
        print("Home nozzle Y-axis:", home_frame.yaxis)
        print("Home nozzle Z-axis:", home_frame.zaxis)

        print(f"\nORIENTATION_MODE = {ORIENTATION_MODE!r}")
        if ORIENTATION_MODE == "fixed":
            print("Locking every frame to HOME's live orientation.")
            self.toolpath = self.toolpath.with_fixed_orientation(home_frame)
        elif ORIENTATION_MODE == "radial":
            print("Keeping each frame's own per-point orientation from the tween.")
        else:
            raise ValueError(f"Unknown ORIENTATION_MODE: {ORIENTATION_MODE!r} -- use 'fixed' or 'radial'.")

        print("\nFirst frame:", self.toolpath.first)

    def step_3_move_safe(self):
        self.robot.abb.send_and_wait(rrc.PrintText("Moving to safe toolpath frame"))
        safe_frame = self.toolpath.safe_frame(self.toolpath.first)
        self.robot.move_to_frame(safe_frame, APPROACH_SPEED, "safe toolpath frame")
        print("STEP 3 completed: Robot moved to safe frame.")

    def step_4_move_first(self):
        self.robot.abb.send_and_wait(rrc.PrintText("Moving to first toolpath frame"))
        self.robot.move_to_frame(self.toolpath.first, APPROACH_SPEED, "first toolpath frame")
        print("STEP 4 completed: Robot moved to first toolpath frame.")

    def step_5_follow_toolpath(self):
        self.robot.abb.send_and_wait(rrc.PrintText("Following movement toolpath"))

        remaining_frames = self.toolpath.remaining
        total_frames = len(self.toolpath)

        pump_started = False
        spray_started = False

        try:
            self.robot.pump_on()
            pump_started = True

            print("\nWaiting", PUMP_START_DELAY, "seconds before opening the air valve.", flush=True)
            self.robot.abb.send_and_wait(rrc.WaitTime(PUMP_START_DELAY))

            self.robot.spray_on()
            spray_started = True

            for index, frame in enumerate(remaining_frames, start=2):
                is_last_frame = index == total_frames
                print("Sending frame", index, "of", total_frames, flush=True)

                zone = rrc.Zone.FINE if is_last_frame else rrc.Zone.Z10
                command = rrc.MoveToFrame(frame, speed=TOOLPATH_SPEED, zone=zone, motion_type=rrc.Motion.LINEAR)

                if is_last_frame:
                    self.robot.abb.send_and_wait(command)
                else:
                    self.robot.abb.send(command)
        finally:
            if pump_started:
                try:
                    self.robot.pump_off()
                except Exception as error:
                    print("Could not turn pump OFF:", error, flush=True)
            if spray_started:
                try:
                    self.robot.spray_off()
                except Exception as error:
                    print("Could not turn spray OFF:", error, flush=True)

        joints, external_axes = self.robot.get_joints()
        print("Complete toolpath finished.", flush=True)
        print("Final toolpath robot joints:", joints, flush=True)

        final_safe_frame = self.toolpath.safe_frame(self.toolpath.last)

        self.robot.abb.send_and_wait(rrc.PrintText("Retracting from toolpath"))
        self.robot.move_to_frame(final_safe_frame, APPROACH_SPEED, "final safe frame")

        self.robot.abb.send_and_wait(rrc.PrintText("Returning to home configuration"))
        self.robot.move_to_home()

        final_joints, final_external_axes = self.robot.get_joints()
        print("Robot returned to HOME_CONFIG.", flush=True)
        print("Final robot joints:", final_joints, flush=True)


############## Main ##############

def main():
    data_file = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_processed_path()

    toolpath = Toolpath.from_json(data_file)
    toolpath.check()

    if MODE == "preview":
        print("\n=== PREVIEW MODE -- no robot connection will be made ===")
        print(f"ORIENTATION_MODE = {ORIENTATION_MODE!r}")

        if ORIENTATION_MODE == "fixed":
            print("Fixed-mode preview uses the FIRST frame's own orientation as a stand-in")
            print("for HOME's live orientation -- the real one is only known once connected.")
            oriented = toolpath.with_fixed_orientation(toolpath.first)
        elif ORIENTATION_MODE == "radial":
            oriented = toolpath
        else:
            raise ValueError(f"Unknown ORIENTATION_MODE: {ORIENTATION_MODE!r} -- use 'fixed' or 'radial'.")

        preview_toolpath = oriented.with_approach_and_retract()
        print(f"Preview includes retracted approach/retract frames -- {SAFE_OFFSET} mm toward SPHERE_CENTER.")
        show_comparison(
            preview_toolpath.frames, preview_toolpath.frames,
            sphere_center=SPHERE_CENTER, safety_radius=SAFETY_RADIUS,
        )
        return

    if MODE != "execute":
        raise ValueError(f"Unknown MODE: {MODE!r} -- use 'preview' or 'execute'.")

    print("\n=== EXECUTE MODE -- connecting to robot ===")
    print(f"ORIENTATION_MODE = {ORIENTATION_MODE!r}")
    try:
        with RobotSession() as robot:
            ToolpathExecutor(robot, toolpath).run(TEST_STEP)
        print("\n=== SELECTED MOVEMENT TEST COMPLETED SUCCESSFULLY ===")
    except KeyboardInterrupt:
        print("\nMovement test stopped manually.")
    except Exception as error:
        print("\nROBOT MOVEMENT TEST FAILED:", type(error).__name__, error, flush=True)


if __name__ == "__main__":
    main()