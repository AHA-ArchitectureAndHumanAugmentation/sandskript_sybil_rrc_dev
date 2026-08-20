"""
robot_kinematics.py

Minimal, dependency-light forward kinematics for the ABB GoFa 10
(CRB15000), parsed directly from its URDF. Used to compute where
HOME_CONFIG's joint angles actually put the tool in Cartesian space,
WITHOUT connecting to the real robot -- so preview mode can show it.

Only handles a simple serial chain of revolute + fixed joints (which is
all this arm's URDF contains, base_link -> ... -> tool0). Not a
general-purpose URDF/kinematics library.
"""

import math
import xml.etree.ElementTree as ET
import numpy as np

from compas.geometry import Frame, Point


def _parse_floats(text):
    return [float(x) for x in text.split()]


def _rpy_matrix(rpy):
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def _axis_angle_matrix(axis, angle):
    axis = np.array(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    C = 1 - c
    return np.array([
        [x * x * C + c,     x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, y * y * C + c,     y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, z * z * C + c],
    ])


def _parse_chain(urdf_path, base_link, tip_link):
    """Ordered list of joints from base_link to tip_link, each as a dict:
    name, type, origin_xyz (m), origin_rpy (rad), axis, child."""
    tree = ET.parse(urdf_path)
    root = tree.getroot()

    joints_by_parent = {}
    for joint in root.findall("joint"):
        parent = joint.find("parent").get("link")
        child = joint.find("child").get("link")
        origin_el = joint.find("origin")
        xyz = _parse_floats(origin_el.get("xyz", "0 0 0")) if origin_el is not None else [0, 0, 0]
        rpy = _parse_floats(origin_el.get("rpy", "0 0 0")) if origin_el is not None else [0, 0, 0]
        axis_el = joint.find("axis")
        axis = _parse_floats(axis_el.get("xyz", "0 0 1")) if axis_el is not None else [0, 0, 1]
        joints_by_parent[parent] = {
            "name": joint.get("name"),
            "type": joint.get("type"),
            "origin_xyz": xyz,
            "origin_rpy": rpy,
            "axis": axis,
            "child": child,
        }

    chain = []
    current = base_link
    while current != tip_link:
        if current not in joints_by_parent:
            raise ValueError(f"No joint found from link {current!r} toward {tip_link!r}")
        j = joints_by_parent[current]
        chain.append(j)
        current = j["child"]
    return chain


def forward_kinematics(urdf_path, joint_angles_deg, base_link="base_link", tip_link="tool0"):
    """
    Tool0 Frame (millimeters, base_link-relative -- same convention as
    WORLD_ORIGIN in fixed_geometry.py) for given joint angles (degrees,
    one per REVOLUTE joint in the chain, in order). Fixed joints apply
    automatically, no angle needed for them.
    """
    chain = _parse_chain(urdf_path, base_link, tip_link)

    T = np.eye(4)
    angle_iter = iter(math.radians(a) for a in joint_angles_deg)

    for joint in chain:
        R_origin = _rpy_matrix(joint["origin_rpy"])
        t_origin = np.array(joint["origin_xyz"])
        T_origin = np.eye(4)
        T_origin[:3, :3] = R_origin
        T_origin[:3, 3] = t_origin
        T = T @ T_origin

        if joint["type"] == "revolute":
            angle = next(angle_iter)
            R_joint = _axis_angle_matrix(joint["axis"], angle)
            T_joint = np.eye(4)
            T_joint[:3, :3] = R_joint
            T = T @ T_joint
        # fixed joints: origin already applied above, nothing more to do

    translation_mm = T[:3, 3] * 1000.0
    xaxis = T[:3, 0]
    yaxis = T[:3, 1]
    return Frame(Point(*translation_mm), xaxis, yaxis)
