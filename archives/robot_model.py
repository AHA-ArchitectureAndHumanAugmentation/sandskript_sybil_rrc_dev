"""Real GoFa 10 robot model (CRB15000_10kg_152), loaded from local URDF + STL meshes."""

import math
from pathlib import Path

from compas_robots import RobotModel
from compas_robots.resources import LocalPackageMeshLoader

PROJECT_ROOT = Path(__file__).resolve().parent
ROBOT_MODEL_DIR = PROJECT_ROOT / "robot_model"
ROBOT_PACKAGE = "CRB15000_10kg_152_v1"
ROBOT_URDF = ROBOT_MODEL_DIR / ROBOT_PACKAGE / "CRB15000_10kg_152.urdf"

JOINT_NAMES = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]

HOME_CONFIG_DEG = [90.0, 15.0, -150.0, -5.0, -40.0, -215.0]


def load_robot():
    loader = LocalPackageMeshLoader(str(ROBOT_MODEL_DIR), ROBOT_PACKAGE)
    model = RobotModel.from_urdf_file(str(ROBOT_URDF))
    model.load_geometry(loader)
    return model


def home_configuration(model):
    config = model.zero_configuration()
    for name, degrees in zip(JOINT_NAMES, HOME_CONFIG_DEG):
        config[name] = math.radians(degrees)
    return config