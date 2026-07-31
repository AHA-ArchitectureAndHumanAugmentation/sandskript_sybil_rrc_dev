# 303_send_to_robot.py

Connects to the real ABB GoFa 10 through Docker/ROS, moves it through a toolpath, and controls the spraying pump and valve. This is the only script in the pipeline that actually talks to physical hardware.

> **Safety:** This script controls a physical industrial robot and a pneumatic spraying output. Test each `TEST_STEP` stage separately, use reduced robot speed, keep the emergency stop accessible, and verify the tool, work object, offsets, and workspace before executing the complete toolpath.

## Known issue -- read this before running against a real path

`302_process_toolpath.py` already applies `TOOLPATH_OFFSET` and adds safe approach/retract frames before saving to `data/processed/`. This script **also** applies `TOOLPATH_OFFSET` and adds its own safe frames. If you point it at a `data/processed/` file, the path will be **shifted twice** and end up with a **redundant second pair of safe frames** -- not yet resolved.

Until this is fixed, either:
- Remove the offset/safe-frame logic in this script (`302` already did it), or
- Point this script at a `data/compas/` file instead of `data/processed/`

See `TODO.md` for the related decision about whether `TOOLPATH_OFFSET` should exist at all, depending on whether `wobj_SprayingNet` gets calibrated on the real controller.

## Usage

```bash
python 303_send_to_robot.py
python 303_send_to_robot.py data/processed/2026-07-27_11-50-11_processed.json
```

No argument defaults to `data/processed/path_processed.json`. Requires the Docker/ROS services running first (`docker compose up -d` from the `docker/` folder) and the ABB controller reachable.

## Constants

| Constant | Value | Purpose |
|---|---|---|
| `HOME_CONFIG` | `[90.0, 15.0, -150.0, -5.0, -40.0, -215.0]` | Joint configuration (degrees) used before and after spraying |
| `TOOL_NAME` | `"t_SprayingTool"` | ABB tool-data name for the spraying tool |
| `WORK_OBJECT` | `"wobj_SprayingNet"` | ABB work-object name for the spraying surface |
| `SPRAY_OUTPUT` | `"ABB_Scalable_IO_0_DO1"` | Digital output controlling the spray valve |
| `PUMP_OUTPUT` | `"ABB_Scalable_IO_0_DO2"` | Digital output controlling the pump |
| `HOME_SPEED` | `300` mm/s | Joint movement to and from home |
| `APPROACH_SPEED` | `200` mm/s | Movement to safe and first frames |
| `TOOLPATH_SPEED` | `600` mm/s | Linear movement during spraying |
| `SAFE_OFFSET` | `200.0` mm | Z distance above the path for safe approach/retract |
| `TOOLPATH_OFFSET` | `(-400, 0, 0)` mm | Translation applied to all imported frames -- see Known issue above |
| `TEST_STEP` | `5` | Which stage to run, see table below |

## Test stages (`TEST_STEP`)

| Step | Action |
|---:|---|
| `0` | Test Python-to-ABB communication only |
| `1` | Read current robot joints and external axes |
| `2` | Set tool/work object, move home, capture TCP orientation |
| `3` | Move to the safe frame above the first path point |
| `4` | Move to the first toolpath frame |
| `5` | Turn on spraying, execute the complete path, retract, return home |

Test sequentially (`0 -> 1 -> 2 -> 3 -> 4 -> 5`) for any new setup or path. Do not start at `5` until earlier stages are verified physically.

## Fixed nozzle orientation

After reaching `HOME_CONFIG`, the script reads the robot's real, live TCP orientation and overwrites every frame's orientation with that single value (`apply_fixed_orientation`). This can't happen anywhere earlier in the pipeline -- it's measured from the physical robot, not computed. Grasshopper/`301`/`302` only ever control frame *positions*; this script is the only place orientation is actually decided.

## Spray sequence (`TEST_STEP = 5`)

1. Pump on
2. Wait 2 seconds (material travels through the hose)
3. Spray valve on
4. Stream through the path with blended motion (`Zone.Z10`), stopping precisely (`Zone.FINE`) only at the last frame
5. Pump and spray off, wrapped in `try/finally` so this happens even if a movement error occurs mid-path
6. Retract to a safe frame above the last point, return to `HOME_CONFIG`

## Related files

- `302_process_toolpath.py` -- produces the `data/processed/` files this script normally reads, and already applies the offset/safe-frame logic duplicated here (see Known issue)
- `robot_geometry.py` -- the sphere-based spray orientation math, not yet wired into this script
- `docker/docker-compose.yml` -- the ROS/ABB driver services this script connects to
- `TODO.md` -- tracks the offset-doubling fix and the `wobj_SprayingNet` calibration question
