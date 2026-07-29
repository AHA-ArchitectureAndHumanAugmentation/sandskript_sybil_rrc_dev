# 304_visualize_toolpath.py

A standalone tool for previewing a toolpath JSON file in 3D **before** running it on the real robot. It does not require Docker, ROS, or a robot connection — it only reads a JSON file and opens a `compas_viewer` window.

## What it's for

`302_send_to_robot.py` applies a series of transformations to a toolpath before the robot ever moves: a global offset, safe approach/retract frames, and (further inside the script) a fixed nozzle orientation. It's easy to lose track of what the geometry actually looks like at each of these stages, especially when swapping between toolpath files.

This script lets you check any toolpath, at any pipeline stage, without needing the robot, Docker, or the ABB controller reachable.

## Installation

Two dependencies are needed on top of the base `compas_rrc` environment: `compas_viewer` and a pinned version of `PySide6` (the GUI library it's built on).

**1. Add these lines to `env_compas_rrc.yml`**, in the existing `pip:` section at the bottom of the file:

```yaml
  - pip:
      - autobahn==24.4.2
      - roslibpy==1.8.1
      - PySide6==6.7.3
      - compas_viewer
```

**2. Update the environment:**

```bash
conda activate compas_rrc
conda env update -f env_compas_rrc.yml --prune
```

### Known issue: `PySide6` DLL load failure on Windows

The newest `PySide6` release (`6.11.1` at time of writing) fails to import on some Windows machines with:

```
ImportError: DLL load failed while importing QtCore: The specified procedure could not be found.
```

This is a known `PySide6` packaging issue, not a problem with this script or with `compas_viewer`. Installing the Microsoft Visual C++ Redistributable does **not** fix it. The fix is to pin `PySide6` to an older, stable release:

```bash
pip uninstall PySide6 PySide6-Addons PySide6-Essentials shiboken6 -y
pip install PySide6==6.7.3
```

Verify both layers independently if you hit this again:

```bash
python -c "from PySide6.QtCore import QTimer; print('PySide6 ok')"
python -c "import compas_viewer; print('compas_viewer works')"
```

## Usage

Run from the repository root, with `compas_rrc` activated:

```bash
python 304_visualize_toolpath.py <path-to-toolpath.json> [--stage raw|offset|full] [--orientation]
```

### Examples

```bash
python 304_visualize_toolpath.py data/toolpath_circle.json
python 304_visualize_toolpath.py data/toolpath_line.json --stage raw
python 304_visualize_toolpath.py converted_toolpath/path_compas_1.json --stage offset
python 304_visualize_toolpath.py data/toolpath_circle.json --orientation
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `file` | Yes | Path to a toolpath JSON file. Relative to the repo root, or absolute. |
| `--stage` | No (default: `full`) | Which pipeline stage to visualize. See below. |
| `--orientation` | No (flag) | Draw each frame as a full axes glyph instead of a plain point. |

### Stages

| Stage | What it shows |
|---|---|
| `raw` | Frames exactly as stored in the JSON file — no transformation. |
| `offset` | `raw` + `TOOLPATH_OFFSET` applied (same `(-400, 0, 0)` mm translation `302_send_to_robot.py` applies before sending anything to the robot). |
| `full` | `offset` + a safe approach frame before the path and a safe retract frame after it (`+SAFE_OFFSET`, 200 mm in Z) — i.e. what the robot's motion actually looks like start to finish. |

`TOOLPATH_OFFSET` and `SAFE_OFFSET` are copied from `302_send_to_robot.py` and kept as constants at the top of this script. **If those values change in `302_send_to_robot.py`, update them here too** — this script does not import `302` directly, since importing it immediately attempts a ROS/robot connection.

### About `--orientation`

The arrows drawn with `--orientation` show each frame's original `xaxis`, exactly as stored in the JSON file. **This is for reference only.** In the real pipeline, `302_send_to_robot.py` discards every frame's orientation and replaces it with whatever direction the nozzle is physically facing at `HOME_CONFIG` (see `README.md` section 7, "Fixed Nozzle Orientation"). The arrows shown here are not what the nozzle will actually do.

## Navigating the viewer

Once the window opens:

- **Drag** with the mouse to orbit around the scene.
- **Scroll** to zoom in and out.
- Check the viewer's **View menu** for preset angles (top / front / right) and other navigation options.
- To save a screenshot, use **View → Capture** in the viewer's own menu. This tool does not auto-save images — screenshots are manual.

## What it draws

| Element | Meaning |
|---|---|
| Gray line | The path connecting every frame in order. |
| Small gray dots | Intermediate frames. |
| Green dot | Start frame. |
| Red dot | End frame. |
| Purple axes glyphs (`--orientation` only) | Each frame's original JSON orientation — reference only, see above. |

## Related files

- `302_send_to_robot.py` — the script that actually sends a toolpath to the robot. `TOOLPATH_OFFSET` and `SAFE_OFFSET` originate here.
- `303_convert_to_compas_json.py` — converts a raw sand-drawing `path.json` into COMPAS frames, which is one of the files you can visualize with this tool.
- `README.md` — main repository documentation, including the full pipeline overview and safety checklist.
