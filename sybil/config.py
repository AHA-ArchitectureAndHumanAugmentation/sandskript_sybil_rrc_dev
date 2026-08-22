"""
Sybil — robot calibration.

Everything here describes THE ROBOT, not a particular run. These values are
calibrated to this specific GoFa and must be identical everywhere they are
used, so they live in one file and nowhere else.

Run-specific toggles (MODE, SPRAY_TYPE, TEST_STEP, ...) do NOT belong here.
They stay at the top of whichever script you are running, where you can see
them.

Lives in the RRC repo only:
    sandskript_sybil_rrc_dev/sybil/config.py
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Robot calibration
#
# CALIBRATED TO THIS ROBOT — confirmed correct by Charlotte.
# Never revert these to Ruth's reference-script values. HOME_CONFIG was a
# different set of joint angles, and WORK_OBJECT was "wobj_SprayingNet",
# which caused wrong-location and singularity errors. Both are fixed here.
# --------------------------------------------------------------------------

HOME_CONFIG = [-89.68, -8.48, -191.38, -0.58, 22.8, -0.25]
TOOL_NAME = "t_SprayingTool"
WORK_OBJECT = "wobj0"

# --------------------------------------------------------------------------
# Digital outputs
# --------------------------------------------------------------------------

SPRAY_OUTPUT = "ABB_Scalable_IO_0_DO1"
PUMP_OUTPUT = "ABB_Scalable_IO_0_DO2"

# --------------------------------------------------------------------------
# Speeds (mm/s)
# --------------------------------------------------------------------------

HOME_SPEED = 300
APPROACH_SPEED = 200
TOOLPATH_SPEED = 600

# --------------------------------------------------------------------------
# Distances (mm) and delays (s)
# --------------------------------------------------------------------------

SAFE_OFFSET = 100.0        # approach/retract standoff, along the normal
PUMP_START_DELAY = 2.0     # pump on -> air valve open

# --------------------------------------------------------------------------
# Paths
#
# REPO_ROOT is the folder above sybil/, so these resolve correctly no matter
# which directory a script is started from.
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

IN_DIR = REPO_ROOT / "data" / "in"
COMPAS_DIR = REPO_ROOT / "data" / "compas"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
EXECUTED_DIR = REPO_ROOT / "data" / "executed"
TILES_DIR = REPO_ROOT / "data" / "tiles"
SURFACES_DIR = REPO_ROOT / "surfaces"

# Used only to work out where HOME_CONFIG lands in Cartesian space, offline,
# for the preview viewer. Never used when connected to the robot.
HOME_URDF_PATH = (
    REPO_ROOT / "archives" / "robot_model" / "CRB15000_10kg_152_v1" / "CRB15000_10kg_152.urdf"
)


# --------------------------------------------------------------------------
# Check: python sybil/config.py
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print("Repo root:", REPO_ROOT)
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
