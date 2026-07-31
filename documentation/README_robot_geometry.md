# robot_geometry.py

Shared geometry configuration: the sphere used for spray orientation, and the world/work-object reference frame. Not run directly -- imported by other scripts.

## What it's for

A single place for all the geometric constants that other scripts need, so changing a coordinate or orientation rule means editing one line here, not hunting through logic spread across multiple files.

## The sphere-based spray orientation

Path points sit at their real, bent position on S.GA (Sybil's Garden Area) -- that projection happens upstream, in Lin's `depth-cam-to-robot` repo. This module only decides:

- **Spray direction** -- which way the nozzle sprays: away from `SPHERE_CENTER`, outward through the point
- **Nozzle position** -- where the nozzle actually sits: the point, pulled toward `SPHERE_CENTER` by `STANDOFF_DISTANCE`, giving clearance off the S.GA surface

The sphere sits behind S.GA, a little offset from the robot's own centre.

## Constants

| Constant | Current value | Meaning |
|---|---|---|
| `SPHERE_CENTER` | `Point(0.0, 0.0, 0.0)` -- placeholder | Sits behind S.GA, offset from robot centre |
| `SPHERE_RADIUS` | `1000.0` mm -- placeholder | Centre to S.GA surface |
| `STANDOFF_DISTANCE` | `100.0` mm -- placeholder | Nozzle clearance, measured from S.GA |
| `DEFAULT_WOBJ_ORIGIN` | `[0.0, 0.0, 0.0]` | World/work-object origin |
| `DEFAULT_WOBJ_XAXIS` | `[1000.0, 0.0, 0.0]` | World/work-object X axis |
| `DEFAULT_WOBJ_YAXIS` | `[0.0, 1000.0, 0.0]` | World/work-object Y axis |

All three sphere values are placeholders, pending real measurements from Rhino. See `TODO.md` -- there's an active plan to set the robot's physical base as Rhino's world `0,0,0`, in which case `SPHERE_RADIUS` should become the GoFa 10's real reach from its datasheet (`1620mm` to the flange, plus tool length).

## Functions

| Function | What it does |
|---|---|
| `spray_direction(point)` | Direction the nozzle sprays: away from `SPHERE_CENTER`, outward through `point` |
| `nozzle_position(point)` | Where the nozzle sits: `point`, pulled toward `SPHERE_CENTER` by `STANDOFF_DISTANCE` |
| `oriented_frame(point, tangent)` | Combines both into a real `Frame`, using `tangent` as the frame's other axis (same `cross_vectors` trick `301_toolpath_generator.ghx` already uses) |

## Status: not yet wired into the pipeline

None of these functions are currently called by `301` or `302` -- the sphere-based orientation exists here, ready, but every frame moving through the pipeline today still carries whatever orientation it had straight from conversion. Turning this on requires real `SPHERE_CENTER`/`SPHERE_RADIUS`/`STANDOFF_DISTANCE` values first.

## Related files

- `301_convert_to_compas_json.py` -- uses `DEFAULT_WOBJ_ORIGIN/XAXIS/YAXIS` when building the wobj info in converted files
- `302_process_toolpath.py` -- where `oriented_frame()` would eventually get called, once real sphere values are set
- `TODO.md` -- tracks the pending Rhino measurements and the robot-base-as-origin plan
