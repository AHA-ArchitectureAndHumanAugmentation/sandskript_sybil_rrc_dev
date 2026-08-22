"""
Sybil — robot calibration.

WHAT THIS FILE IS FOR
Everything here describes THE ROBOT, not a particular run. These values are
calibrated to this specific GoFa and must be identical everywhere they are
used, so they live in one file and nowhere else. Change a number here and
every script picks it up.

WHAT DOES NOT BELONG HERE
Run-specific toggles — MODE, SPRAY_TYPE, TEST_STEP and so on. Those stay at
the top of whichever script you are running, where you can see them next to
the thing they affect.

Lives in the RRC repo only:
    sandskript_sybil_rrc_dev/sybil/config.py
"""

from pathlib import Path


# ==========================================================================
# SETTINGS
# ==========================================================================

# --- Robot calibration ---------------------------------------------------
#
# CALIBRATED TO THIS ROBOT — confirmed correct by Charlotte.
# Do not revert these to Ruth's reference-script values. HOME_CONFIG was a
# different set of joint angles, and WORK_OBJECT was "wobj_SprayingNet",
# which caused wrong-location and singularity errors. Both are fixed here.

HOME_CONFIG = [-89.68, -8.48, -191.38, -0.58, 22.8, -0.25]
# The six joint angles, in degrees, that put the robot in its resting pose.
# The robot returns here between every toolpath. Changing these moves where
# the arm parks — get it wrong and it can park inside the structure.

TOOL_NAME = "t_SprayingTool"
# The tool defined on the robot controller. Tells the robot where the spray
# nozzle sits relative to the flange, so frames land at the nozzle tip and
# not at the wrist. Must match the name on the controller exactly.

WORK_OBJECT = "wobj0"
# The coordinate system all frames are measured in. wobj0 is the robot's own
# base. If this is wrong, every frame lands in the wrong place — this was
# the cause of an earlier round of wrong-location and singularity errors.


# --- Digital outputs -----------------------------------------------------
#
# The names of the controller's output signals. Must match the controller
# configuration exactly, or the pump and valve simply never switch.

SPRAY_OUTPUT = "ABB_Scalable_IO_0_DO1"
# The air valve. Opens to atomise the mixture.

PUMP_OUTPUT = "ABB_Scalable_IO_0_DO2"
# The material pump. Started first, before the air valve.


# --- Speeds (mm/s) -------------------------------------------------------

HOME_SPEED = 300
# How fast the arm travels to and from its home pose. Not spraying, so this
# is about time and safety rather than material. Higher = shorter day,
# faster movement near the structure.

APPROACH_SPEED = 200
# How fast it moves from the safe frame down to the first point of a path.
# Deliberately slower than travel: this is the move that comes closest to
# the net before spraying starts.

TOOLPATH_SPEED = 600
# How fast it moves WHILE SPRAYING. This is the important one.
# Slower = more material per millimetre, thicker line, longer cycle time.
# Faster = thinner line, shorter cycle time.
# Changing this changes both how the piece looks and whether the day fits
# in its schedule.


# --- Distances (mm) and delays (s) ---------------------------------------

SAFE_OFFSET = 100.0
# How far back from the surface the "safe frame" sits, measured along the
# surface normal. The arm approaches and retracts through this point so it
# never drives straight at the net. Larger = safer but slower.

PUMP_START_DELAY = 2.0
# How long to run the pump before opening the air valve, so material has
# reached the nozzle by the time spraying begins.
# Too short = the first part of the path sprays air and comes out thin.
# Too long = material pools at the nozzle and the path starts with a blob.


# ==========================================================================


# --------------------------------------------------------------------------
# Paths
#
# Worked out from where this file sits, so they are correct no matter which
# folder a script is started from. Not settings — do not edit unless the
# repo layout itself changes.
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

IN_DIR = REPO_ROOT / "data" / "in"                 # raw captures arriving
COMPAS_DIR = REPO_ROOT / "data" / "compas"         # after 301, converted
PROCESSED_DIR = REPO_ROOT / "data" / "processed"   # after 302, ready to run
EXECUTED_DIR = REPO_ROOT / "data" / "executed"     # what has been sprayed
TILES_DIR = REPO_ROOT / "data" / "tiles"           # tile status bookkeeping
SURFACES_DIR = REPO_ROOT / "surfaces"              # tile_*.obj meshes

# Used only to work out where HOME_CONFIG lands in Cartesian space, offline,
# for the preview viewer. Never used when connected to the robot.
HOME_URDF_PATH = (
    REPO_ROOT / "archives" / "robot_model" / "CRB15000_10kg_152_v1" / "CRB15000_10kg_152.urdf"
)


# --------------------------------------------------------------------------
# Check: python sybil/config.py
#
# Prints the settings and checks that every folder actually exists.
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print("Repo root:", REPO_ROOT)
    print()
    print("Tool:        ", TOOL_NAME)
    print("Work object: ", WORK_OBJECT)
    print("Home config: ", HOME_CONFIG)
    print("Speeds:       home={} approach={} toolpath={} mm/s".format(
        HOME_SPEED, APPROACH_SPEED, TOOLPATH_SPEED))
    print("Safe offset:  {} mm".format(SAFE_OFFSET))
    print()
    for name, path in [
        ("data/in", IN_DIR),
        ("data/compas", COMPAS_DIR),
        ("data/processed", PROCESSED_DIR),
        ("data/executed", EXECUTED_DIR),
        ("data/tiles", TILES_DIR),
        ("surfaces", SURFACES_DIR),
        ("home URDF", HOME_URDF_PATH),
    ]:
        mark = "ok     " if path.exists() else "MISSING"
        print("{}  {:<12} {}".format(mark, name, path))
