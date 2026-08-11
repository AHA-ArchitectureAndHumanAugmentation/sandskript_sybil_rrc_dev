# Sybil Capture 2 Robot 

This repository contains the toolpath pipeline developed for Sybil developed 
for Ars Electronica 2026. It converts a visitor's
captured drawing into a spray path on one tile of a microgreens garden,
executes it on an ABB GoFa robot through a Docker-based ROS setup, records
what actually ran, and automatically selects which tile to work on next,
looping back to the depth-camera capture pipeline via a lightweight ZeroMQ
message layer.

Built from Ruth's original `sandskript_compas_rrc` repository as a starting
point; substantially restructured since.
See Repository Structure and
Workflow below for what changed.

The repository contains:

- `301` / `302` / `304`: convert → process → execute the toolpath
- A tile tracking & selection system (which tile, how many times, what's next)
- A ZeroMQ message layer connecting to Lin's depth-camera capture pipeline
- A blocking 3D checkpoint viewer at every stage
- Standalone testing tools for exercising the pipeline without Rhino,
  without access to Image Capturing, and without the robot connected
- A Conda environment for the Python dependencies
- A Docker Compose configuration for ROS, rosbridge, and the ABB driver

> **Safety:** This repository controls a physical industrial robot and a
> pneumatic spraying output. Test each stage separately (`TEST_STEP` 0
> through 5), keep `304_send_to_robot.py`'s `MODE` on `"preview"` until you
> deliberately mean to run the real robot, use reduced robot speed, keep the
> emergency stop accessible, and verify the tool, work object, and
> workspace before executing a complete toolpath.

## Repository Structure

```text
sandskript_sybil_rrc_dev/
├── main.py                         # Entry point: single run, or the autonomous ZeroMQ loop
├── pipeline_utils.py                # Shared 301 -> 302 -> 304 sequence, imported everywhere
├── fixed_geometry.py                 # Single shared world origin + safety sphere
├── view_utils.py                     # Blocking 3D checkpoint viewer
├── 301_convert_to_compas_json.py     # Raw capture -> COMPAS frames
├── 302_process_toolpath.py           # Tween + safety clamp -> robot-ready JSON
├── 304_send_to_robot.py              # Preview / execute against the real robot
├── tile_status.py                    # Spray history, read live from data/executed/
├── tile_selector.py                  # Picks + records the next tile
├── tile_announcer.py                 # Sends the selection to Lin
├── tile_reciever.py                  # Stand-in for Lin's real receiver (name misspelled on disk)
├── 300_watch_and_run.py              # Filesystem-polling trigger (no ZeroMQ)
├── 300b_zmq_listener.py              # Standalone test receiver, inbound direction
├── 300b_zmq_publisher.py             # Standalone test sender, inbound direction
├── 301b_flat_path_to_tile.py         # Synthetic test path generator, no Rhino needed
├── 301_toolpath_generator.ghx        # Grasshopper: exports a curve as a raw capture JSON
├── 304_toolpath_generator_CT.gh      # Grasshopper: tween/morph prototype (now ported into 302)
├── env_compas_rrc.yml                # Conda environment definition
├── documentation/                    # Topic docs -- start with README_pipeline.md
├── sybil_geo/                        # surface.obj, the physical spray-surface mesh
├── archives/                         # Ruth's original reference scripts, kept for orientation
├── data/
│   ├── in/                           # Raw captures land here (Lin, Grasshopper, or test tools)
│   ├── compas/                       # 301's output
│   ├── processed/                    # 302's output -- what actually gets sent to 304
│   ├── executed/                     # 304's saved copy of every real spray
│   └── tiles/selections/             # Every tile-selection decision, saved
└── docker/
    └── docker-compose.yml
```

## Workflow

```text
Depth camera captures a drawing (Lin's pipeline)
        ↓
Sent over ZeroMQ, port 5557
        ↓
301: raw capture -> COMPAS frames
        ↓
302: tween morph + safety clamp -> robot-ready JSON
        ↓
Blocking 3D preview (view_utils.py) -- closed manually before continuing
        ↓
304: connect to ROS and ABB (only if MODE = "execute")
        ↓
Capture the nozzle orientation at HOME_CONFIG (if ORIENTATION_MODE = "fixed")
        ↓
Approach the toolpath safely
        ↓
Turn the spray output ON
        ↓
Follow the blended linear toolpath
        ↓
Turn the spray output OFF
        ↓
Retract and return home
        ↓
Record what actually ran -> data/executed/
        ↓
Select the next tile, checked against spray-frequency limits
        ↓
Announce the next tile to Lin over ZeroMQ, port 5558
        ↓
(loop back to the top)
```

## 1. Requirements

### Software

- Windows
- Conda or Miniconda
- Docker Desktop
- Rhino 8
- Grasshopper
- ABB RobotWare system configured for `compas_rrc`

### Hardware

- ABB GoFa robot
- ABB controller and FlexPendant
- Spraying tool configured on the robot
- Pneumatic valve connected to a robot digital output
- Computer connected to the ABB controller network

## 2. Install the Conda Environment

Open Anaconda Prompt or a terminal in the repository folder.

Create the environment:

```bash
conda env create -f env_compas_rrc.yml
```

Activate it:

```bash
conda activate compas_rrc
```

**`pyzmq` is not yet in `env_compas_rrc.yml`** — it was added during
development via a direct `pip install` and never folded back into the
environment file. Install it manually until that's fixed:

```bash
pip install pyzmq --break-system-packages
```

Verify the main imports:

```bash
python -c "import compas; import compas_rrc; import compas_fab; import roslibpy; import zmq; print('Environment works')"
```

To update an existing environment after modifying the YAML file:

```bash
conda env update -f env_compas_rrc.yml --prune
```

The environment includes (carried over from the original setup — confirm
against your actual `env_compas_rrc.yml` if in doubt):

| Package | Version | Purpose |
|---|---:|---|
| Python | 3.12.12 | Python runtime |
| COMPAS | 2.14.1 | Geometry and data framework |
| compas_rrc | 2.0.0 | Communication with ABB through ROS |
| compas_fab | 1.1.0 | Robotic fabrication tools |
| compas_robots | 0.6.0 | Robot-model tools |
| roslibpy | 1.8.1 | Python connection to rosbridge |
| Autobahn | 24.4.2 | WebSocket communication |
| pyzmq | — | Tile-selection messaging (installed manually, see above) |

## 3. Start the ROS and ABB Services

The Docker configuration starts three services:

| Service | Purpose | Port |
|---|---|---:|
| `ros-master` | Runs `roscore` | `11311` |
| `ros-bridge` | Runs the rosbridge WebSocket server | `9090` |
| `abb-driver` | Connects ROS to the ABB controller | ABB streaming/state ports |

From the repository folder, start the services with:

```bash
cd docker
docker compose up
```

To run them in the background:

```bash
docker compose up -d
```

To stop them:

```bash
docker compose down
```

The current ABB driver configuration uses:

```yaml
robot_ip: 192.168.125.1
robot_streaming_port: 30101
robot_state_port: 30201
namespace: rob1
```

`192.168.125.1` is configured as the real controller service-port address.
Change `robot_ip` in `docker/docker-compose.yml` when using another
controller address or a virtual controller.

## 4. Generate a Toolpath

A raw capture can come from three places:

| Source | How |
|---|---|
| Lin's real pipeline | Sent automatically over ZeroMQ once her side is wired up — see `documentation/README_messaging.md` |
| Manual Grasshopper export | Open `301_toolpath_generator.ghx`, set `tile_id`, click Save |
| Synthetic test path | `python 301b_flat_path_to_tile.py test_path.json --tile-id 2` — no Rhino needed |

All three land in `data/in/<timestamp>/path.json`, in the same raw format
either way — see Toolpath Data Format below.

## 5. Toolpath Data Format

**Raw capture** (what lands in `data/in/`) — a list of strokes, each a list
of points as planes:

```json
{
  "tile_id": 2,
  "strokes": [
    [
      { "plane": { "origin": [200.0, 500.0, 0.0], "xaxis": [1.0, 0.0, 0.0], "yaxis": [0.0, -1.0, 0.0] } }
    ]
  ]
}
```

`tile_id` is optional — if absent, it stays `None` all the way through the
pipeline, and 304 will skip spray recording rather than guess which tile it
belongs to.

**Converted / processed frames** (301's and 302's output) — a flat list of
COMPAS `Frame` objects:

```json
{
  "frames": [
    {
      "dtype": "compas.geometry/Frame",
      "data": {
        "point": [200.0, 500.0, 0.0],
        "xaxis": [1.0, 0.0, 0.0],
        "yaxis": [0.0, -1.0, 0.0]
      }
    }
  ],
  "tile_id": 2
}
```

| Attribute | Type | Description |
|---|---|---|
| `point` | `[x, y, z]` | TCP position in millimetres |
| `xaxis` | `[x, y, z]` | Frame X-axis |
| `yaxis` | `[x, y, z]` | Frame Y-axis |
| `frames` | list | Ordered robot targets |
| `tile_id` | int or null | Which tile this path belongs to |

## 6. Configure the Robot Script

Open `304_send_to_robot.py`.

### Robot definitions

```python
HOME_CONFIG = [-89.68, -8.48, -191.38, -0.58, 22.8, -0.25]
TOOL_NAME = "t_SprayingTool"
WORK_OBJECT = "wobj0"
SPRAY_OUTPUT = "ABB_Scalable_IO_0_DO1"
PUMP_OUTPUT = "ABB_Scalable_IO_0_DO2"
```

These are calibrated to the real robot — **never revert them** to older
reference values (an earlier version of this script used a different
`HOME_CONFIG` and `WORK_OBJECT = "wobj_SprayingNet"`; both were wrong for
this setup).

| Parameter | Purpose |
|---|---|
| `HOME_CONFIG` | Joint configuration used before and after spraying |
| `TOOL_NAME` | ABB tool-data name for the spraying tool |
| `WORK_OBJECT` | ABB work-object name for the spraying surface |
| `SPRAY_OUTPUT` | ABB digital output controlling the spray valve |
| `PUMP_OUTPUT` | ABB digital output controlling the pump, turned on first |

### Movement parameters

```python
HOME_SPEED = 300
APPROACH_SPEED = 200
TOOLPATH_SPEED = 600
SAFE_OFFSET = 100.0
```

| Parameter | Current value | Purpose |
|---|---:|---|
| `HOME_SPEED` | 300 mm/s | Joint movement to and from home |
| `APPROACH_SPEED` | 200 mm/s | Movement to safe and first frames |
| `TOOLPATH_SPEED` | 600 mm/s | Linear movement during spraying |
| `SAFE_OFFSET` | 100 mm | Retreat distance for approach/retract frames |

**There is no `TOOLPATH_OFFSET` anymore.** Positioning and reach are
handled entirely by 302's tween/safety-clamp math (see
`documentation/README_pipeline.md`) — nothing in 304 manually shifts the
path.

**The safe frame no longer translates straight up in Z.** It retreats
toward `SPHERE_CENTER` (from `fixed_geometry.py`), computed fresh from each
point's actual position:

```python
direction = Vector.from_start_end(frame.point, SPHERE_CENTER)
direction.unitize()
safe_point = frame.point + direction * SAFE_OFFSET
```

### Select the input file

The script auto-picks the most recently modified file in `data/processed/`:

```python
def latest_processed_path():
    files = sorted(PROCESSED_DIR.glob("*_processed.json"), key=lambda p: p.stat().st_mtime)
    return files[-1]
```

To use a specific file instead, pass it as an argument:

```bash
python 304_send_to_robot.py data/processed/some_file_processed.json
```

## 7. Nozzle Orientation

`ORIENTATION_MODE` controls this, switchable for testing either way:

```python
ORIENTATION_MODE = "radial"   # or "fixed"
```

- **`"radial"`** (default) — every frame keeps its own per-point
  orientation from the tween, pointing outward from the shared center.
  Matches what the preview viewer shows.
- **`"fixed"`** — after the robot reaches `HOME_CONFIG`, the script reads
  the live TCP orientation and applies it to every frame, exactly like the
  original design: Grasshopper controls position, the home orientation
  controls the nozzle direction throughout.

Before running a complete path in `"fixed"` mode, confirm the nozzle
orientation at home is correct for spraying.

## 8. Test Stages

Select the stage with:

```python
TEST_STEP = 5
```

| Step | Action |
|---:|---|
| `0` | Test Python-to-ABB communication |
| `1` | Read current robot joints and external axes |
| `2` | Set the tool/work object, move home, resolve orientation |
| `3` | Move to the safe frame above the first path point |
| `4` | Move to the first toolpath frame |
| `5` | Turn on spraying, execute the complete path, retract, return home, record, select next tile, announce it |

For a new setup or path, test sequentially: `0 → 1 → 2 → 3 → 4 → 5`. Do not
start at `5` until the previous stages have been verified physically.

`MODE` governs whether any of this touches the real robot at all —
`"preview"` never connects; only `"execute"` does. See
`documentation/README_testing.md` for the full set of safety flags.

## 9. Run the Robot Program

Confirm that:

1. Docker services are running.
2. The ABB controller is reachable.
3. The correct tool and work object exist.
4. The digital output names are correct.
5. The robot workspace is clear.
6. The correct processed file is selected (or the latest one is the intended one).
7. `tile_id` is present in that file, if you want the loop to continue automatically.
8. `TEST_STEP` and `MODE` are set appropriately.
9. `tile_reciever.py` is running in another terminal, if you want the next-tile announcement to be received.

Activate the environment and run:

```bash
conda activate compas_rrc
python 304_send_to_robot.py
```

The script connects to:

```python
abb = rrc.AbbClient(ros, "/rob1")
```

The `/rob1` namespace must match the namespace in `docker/docker-compose.yml`.

## 10. Complete Movement Sequence

With `TEST_STEP = 5` and `MODE = "execute"`, the program performs:

1. Connect to ROS and ABB.
2. Verify communication.
3. Read the current robot joints.
4. Set `t_SprayingTool` and `wobj0`.
5. Set acceleration to `20, 20`.
6. Move to `HOME_CONFIG`.
7. Resolve orientation (`ORIENTATION_MODE`).
8. Move to the first safe frame.
9. Move to the first toolpath frame.
10. Turn the pump ON, wait `PUMP_START_DELAY` seconds, turn the spray valve ON.
11. Stream the intermediate frames with linear blended movement.
12. Stop precisely at the final frame.
13. Turn the spray valve OFF, then the pump OFF.
14. Move to a safe frame above the final point.
15. Return to `HOME_CONFIG`.
16. Save a full copy of the executed toolpath to `data/executed/`.
17. Select the next tile, checked against spray-frequency limits.
18. Announce the next tile to Lin over ZeroMQ.

## 11. Continuous Toolpath Motion

Intermediate targets use:

```python
abb.send(
    rrc.MoveToFrame(
        frame,
        speed=TOOLPATH_SPEED,
        zone=rrc.Zone.Z10,
        motion_type=rrc.Motion.LINEAR,
    )
)
```

This provides linear TCP movement, a `Z10` blending zone, queued commands
through `abb.send(...)`, and smoother motion without a complete stop at
every intermediate frame.

The final target uses:

```python
abb.send_and_wait(
    rrc.MoveToFrame(
        frame,
        speed=TOOLPATH_SPEED,
        zone=rrc.Zone.FINE,
        motion_type=rrc.Motion.LINEAR,
    )
)
```

This makes the robot reach and stop at the exact final frame before the
spraying output is turned off.

## 12. Spray Output Control

Two outputs, turned on in sequence with a short delay between them — the
pump first, so material has time to reach the nozzle before the valve
opens:

```python
robot.pump_on()
abb.send_and_wait(rrc.WaitTime(PUMP_START_DELAY))
robot.spray_on()
```

Both are wrapped in `try/finally`, so the script attempts to turn both off
even if a robot movement raises an error:

```python
try:
    pump_on(); spray_on()
    # robot movement
finally:
    spray_off(); pump_off()
```

This is a software safeguard only. The pneumatic system must still have
appropriate physical safety controls.

## Troubleshooting

### Conda environment already exists

```bash
conda env update -f env_compas_rrc.yml --prune
```

### `ModuleNotFoundError: No module named 'zmq'`

`pyzmq` isn't in `env_compas_rrc.yml` yet — see Install the Conda
Environment above.

### `ModuleNotFoundError` (anything else)

```bash
conda activate compas_rrc
python -c "import compas_rrc; print(compas_rrc.__version__)"
```

### Docker services do not connect

```bash
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs
```

Confirm Docker Desktop is running, port `9090` is available, the ABB
controller is reachable, and the namespace is `rob1`.

### A script hangs with no error, right after "Announced tile X"

`tile_announcer.py` is waiting to deliver a message with nothing connected
to receive it. Start `tile_reciever.py` first, before anything that
announces a tile. This shouldn't hang *forever* anymore (`LINGER` is set),
but it will still wait up to a second before giving up — see
`documentation/README_messaging.md`.

### The wrong capture gets picked up after a `git checkout`

`git checkout` resets every file's modified-time, even unchanged ones.
`main.py` and `300b_zmq_publisher.py` both sort `data/in` by the timestamp
in the *folder name*, not modified-time, specifically to avoid this — if
something else in the repo ever needs "the newest file," use the same
approach.

### An edit doesn't seem to take effect

Confirm it actually saved to disk before assuming it's a caching problem:

```powershell
Get-Content the_file.py | Select-String "the thing you added"
```

An unsaved editor tab and a stale `__pycache__` look identical from the
outside.

### JSON file is not found / does not contain frames / toolpath contains no frames

Same as before — the data folder must be beside the script, the root JSON
object must contain a `frames` list, and the program intentionally stops
if that list is empty. Regenerate from Grasshopper, `301b`, or a real
capture.

### Robot moves to the wrong location

Check `WORK_OBJECT`, the JSON coordinates, ABB work-object calibration,
millimetre units, `SPHERE_CENTER`/`SAFETY_RADIUS` in `fixed_geometry.py`,
and the first/last frames printed by the script.

### Nozzle points in the wrong direction

Check `ORIENTATION_MODE`. In `"fixed"` mode, verify the home nozzle
orientation before moving. In `"radial"` mode, this is derived
geometrically from `SPHERE_CENTER` — confirm that's still correct.

### Robot pauses between points

Confirm intermediate targets use `abb.send(...)`, `zone=rrc.Zone.Z10`,
`motion_type=rrc.Motion.LINEAR`. The final frame should remain `FINE` and
use `send_and_wait(...)`.

### Spray does not activate

Check `SPRAY_OUTPUT` and `PUMP_OUTPUT` match the ABB signal names exactly,
both outputs are configured and writable in RobotWare, valve wiring and
power supply are correct, the pneumatic supply is connected, and the robot
safety state permits output activation.

## Safety Checklist

Before every physical run:

- [ ] Correct tool mounted and secured
- [ ] Correct ABB tool data selected
- [ ] Correct work object selected and calibrated
- [ ] Correct digital outputs confirmed (pump and spray valve)
- [ ] Air pressure and valve operation checked separately
- [ ] Toolpath file verified, `tile_id` present if the loop should continue
- [ ] First and last frames inspected
- [ ] `ORIENTATION_MODE` and `MODE` set deliberately, not left over from testing
- [ ] Test Steps 0–4 completed successfully
- [ ] Robot speed reduced for the first run
- [ ] Workspace clear of people and obstacles
- [ ] Hose cannot catch, pull, or enter robot joints
- [ ] Emergency stop accessible
- [ ] Spray output confirmed OFF before approaching the robot

## Current Capabilities

- Depth-camera capture ingestion, or manual Grasshopper / synthetic test paths
- Tween-morph toolpath processing with a hard safety-radius clamp
- Two nozzle-orientation modes, switchable for comparison
- Staged robot testing (`TEST_STEP` 0–5), with `MODE` gating any real connection
- Safe approach and retraction frames, computed live toward the shared center
- Continuous blended linear motion
- Pump + spray valve digital output control, sequenced with a start delay
- Automatic output-off attempt after movement errors
- Every real execution recorded, self-contained, in `data/executed/`
- Automatic next-tile selection: rate limits, optional lifetime caps, retry, fallback
- A ZeroMQ message layer to Lin's capture pipeline, both directions
- Docker-based ROS, rosbridge, and ABB driver setup

## Project

**Sandskript — Sybil**
MAS Architecture and Digital Fabrication
ETH Zürich
2026
