# 302_process_toolpath.py

Takes converted COMPAS frames and turns them into a robot-ready toolpath: applies a translation, and adds safe approach/retract frames at the start and end. Shows a before/after comparison in `compas_viewer`.

## What it's for

`301_convert_to_compas_json.py` produces raw, unshifted COMPAS frames. This script is the missing link between that and `303_send_to_robot.py` -- it does the transformations that can be computed offline, ahead of time, without needing the robot connected.

## Usage

```bash
python 302_process_toolpath.py
python 302_process_toolpath.py data/compas/2026-07-27_11-50-11_compas.json
```

No argument defaults to `DEFAULT_INPUT_PATH` (`data/compas/path_compas.json`). Called automatically by `main.py` as the second pipeline stage.

## What it does

| Step | What happens |
|---|---|
| 1 | Loads frames from the input file |
| 2 | Shifts every frame by `TOOLPATH_OFFSET` |
| 3 | Adds a safe frame before the first point and after the last (`SAFE_OFFSET` in Z) |
| 4 | Saves the result to `data/processed/<name>_processed.json` |
| 5 | Shows a `compas_viewer` window: the input (light gray) next to the processed result (dark) |

## Constants

| Constant | Value | Purpose |
|---|---|---|
| `TOOLPATH_OFFSET` | `Vector(0, 0, 400.0)` | Translation applied to every frame -- see the origin/scale discussion in `TODO.md` before changing this |
| `SAFE_OFFSET` | `200.0` mm | Z lift for the safe approach/retract frames only |

## Known issue

`303_send_to_robot.py` re-applies its own `TOOLPATH_OFFSET` and re-adds safe frames on top of what this script already did. Pointing `303` at this script's output will double-shift the path. See `README_303_send_to_robot.md` and `TODO.md`.

`TOOLPATH_OFFSET`'s value itself is under active reconsideration -- if the robot's world object (`wobj_SprayingNet`) gets calibrated so its own origin matches wherever geometry is authored in Rhino, this offset may need to become `Vector(0, 0, 0)` entirely, since no software-side shift would be needed. See `TODO.md`.

## Related files

- `301_convert_to_compas_json.py` -- produces this script's input
- `303_send_to_robot.py` -- consumes this script's output (with the known double-offset caveat above)
- `view_utils.py` -- provides `show_comparison()`, used for the before/after viewer
- `robot_geometry.py` -- the sphere-based spray orientation logic, not yet wired into this script's pipeline
- `TODO.md` -- tracks the `TOOLPATH_OFFSET` decision and the double-offset fix
