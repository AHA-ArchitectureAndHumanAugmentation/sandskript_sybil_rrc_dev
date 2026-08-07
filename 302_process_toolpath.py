#!/usr/bin/env python3
"""Process a converted toolpath into a robot-ready JSON file.

Loads curve A (frames from 301, positioned on the double-curved net) and
morphs it toward a spherical toolpath -- the tween + safety-clamp logic
ported directly from the Grasshopper prototype.

SPHERE_CENTER and SAFETY_RADIUS come from fixed_geometry.py -- the single
source of truth shared with 301/view_utils. TARGET_RADIUS and T are
specific to this tween effect and stay local to this file.

Approach/retract safe frames are NOT added here -- that's 304's job,
computed at execution time from the robot's live measured orientation.
Adding them here too would double them once 304 runs.

Pipeline: 301_convert_to_compas_json.py -> 302_process_toolpath.py -> 304_send_to_robot.py

Usage: python 302_process_toolpath.py data/compas/some_file_compas.json
"""

import sys
from pathlib import Path

from compas.data import json_dump, json_load
from compas.geometry import Frame, Plane

from fixed_geometry import SPHERE_CENTER, SAFETY_RADIUS
from view_utils import show_comparison

ROOT = Path(__file__).resolve().parent

DEFAULT_INPUT_PATH = ROOT / "data" / "compas" / "path_compas.json"
INPUT_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT_PATH

# Strip "_compas" from the name if present, so the next stage's suffix
# reads cleanly: "<name>_compas.json" -> "<name>_processed.json"
BASE_NAME = INPUT_PATH.stem
if BASE_NAME.endswith("_compas"):
    BASE_NAME = BASE_NAME[: -len("_compas")]

############## Constants ##############

TARGET_RADIUS = 1500.0   # radius the toolpath lands on when T = 1.0
T = 0.75                 # blend factor: 0.0 = curve A (original), 1.0 = curve B (on target sphere)


############## Radial Shell ##############

class RadialShell:
    """A center + radius used purely for radial projection/clamping --
    not the physical installation sphere itself, just a math helper."""

    def __init__(self, center, radius):
        self.center = center
        self.radius = radius

    def project(self, point):
        """Returns a new point pushed radially onto this shell's surface."""
        direction = point - self.center
        direction.unitize()
        return self.center + direction * self.radius

    def clamp(self, point):
        """Returns point unchanged if already within radius, otherwise
        pulls it radially in to sit exactly on the shell's surface."""
        direction = point - self.center
        if direction.length <= self.radius:
            return point
        direction.unitize()
        return self.center + direction * self.radius


############## Toolpath Morph ##############

class ToolpathMorph:
    """Morphs curve A's points toward a target shell by blend factor t,
    clamps every point to a safety shell, and rebuilds frames radiating
    outward from the shared center. Produces the SPRAY PATH ONLY --
    no approach/retract frames; 304 owns those."""

    def __init__(self, points_on_surface, center, target_radius, safety_radius):
        self.points_on_surface = points_on_surface
        self.center = center
        self.target_shell = RadialShell(center, target_radius)
        self.safety_shell = RadialShell(center, safety_radius)

    def tween_frames(self, t):
        frames = []
        for point in self.points_on_surface:
            target_point = self.target_shell.project(point)
            blended = point + (target_point - point) * t
            blended = self.safety_shell.clamp(blended)

            normal = blended - self.center
            normal.unitize()
            frames.append(Frame.from_plane(Plane(blended, normal)))
        return frames


############## Main ##############

def main():
    data = json_load(INPUT_PATH)
    if "frames" not in data:
        raise KeyError("The JSON file does not contain 'frames'.")
    original_frames = data["frames"]

    points_on_surface = [frame.point for frame in original_frames]
    morph = ToolpathMorph(points_on_surface, SPHERE_CENTER, TARGET_RADIUS, SAFETY_RADIUS)

    tweened = morph.tween_frames(T)

    outdir = ROOT / "data" / "processed"
    outdir.mkdir(exist_ok=True)
    outfile = outdir / f"{BASE_NAME}_processed.json"
    json_dump({"frames": tweened}, outfile)

    print(f"Saved {len(tweened)} frames to {outfile}")

    show_comparison(
        original_frames, tweened,
        sphere_center=SPHERE_CENTER, target_radius=TARGET_RADIUS, safety_radius=SAFETY_RADIUS,
    )


if __name__ == "__main__":
    main()