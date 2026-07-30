# view_utils.py

Shared `compas_viewer` display logic. Not a standalone script — it's a small module imported by other scripts to show a toolpath as a checkpoint, before moving on to the next pipeline stage. It does not require Docker, ROS, or a robot connection — it only takes a list of COMPAS frames and opens a `compas_viewer` window.

## What it's for

Every stage in the pipeline (`301_convert_to_compas_json.py`, `302_process_toolpath.py`) transforms the toolpath in some way — converting units, applying an offset, adding safe frames. It's easy to lose track of what the geometry actually looks like at each stage. `view_utils.py` gives every stage the same simple way to show its result before continuing.

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

This is a known `PySide6` packaging issue, not a problem with this module or with `compas_viewer`. Installing the Microsoft Visual C++ Redistributable does **not** fix it. The fix is to pin `PySide6` to an older, stable release:

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

Not run directly — imported by other scripts:

```python
from view_utils import show_frames

show_frames(frames)  # frames: a list of compas.geometry.Frame
```

Currently called automatically by:

| Script | When it's called |
|---|---|
| `301_convert_to_compas_json.py` | Before conversion (raw input) and after (converted result). If the input is already in converted format, called once, showing it as-is. |
| `302_process_toolpath.py` | Before processing (input frames) and after (offset + safe frames applied). |

## What it draws

| Element | Meaning |
|---|---|
| Gray line | The path connecting every frame in order. |
| Small gray dots | Intermediate frames. |
| Green dot | Start frame. |
| Red dot | End frame. |

No grid, no per-frame orientation glyphs — see "Why no grid or orientation glyphs" below for why these were removed.

## Reading the terminal output

Every call prints the path's real bounding-box size:
```
Bounding box size (mm): X=181.9, Y=86.7, Z=0.0
```

**This is the reliable way to check scale — not the viewer's visual size.** The camera auto-fits to whatever's loaded, so a 1-meter path and a 1000mm path can look identical in the window. Only these printed millimetre values tell you the truth.

## Why no grid or orientation glyphs

Earlier versions drew a grid, full axes glyphs at every frame, and a fixed 1000mm reference line to compare against. All three were removed:

- **The grid** is a fixed default size unrelated to your data's actual scale — next to a small path, it looks enormous and actively misleading.
- **Frame axes glyphs**, drawn for every frame, used some large fixed length, completely out of proportion to how far apart the actual points were. A ~180mm path with default-sized glyphs looked like a tiny dot buried in a huge colored star.
- **The reference line** tried to fix this by giving a known-size object to compare against, but didn't solve the root problem (everything in the scene gets auto-framed together) and just added clutter.

If orientation needs to come back later, scale it relative to the path's own bounding box (e.g. 10% of its largest dimension) instead of using a fixed length, so it stays proportional at any scale.

## Navigating the viewer

Once the window opens:

- **Drag** with the mouse to orbit around the scene.
- **Scroll** to zoom in and out.
- Check the viewer's **View menu** for preset angles (top / front / right), and a **Camera Settings** dialog if the geometry looks too far away or clipped.
- To save a screenshot, use **View → Capture** in the viewer's own menu. This module does not auto-save images — screenshots are manual.

## Known limitations

- **World origin is shown, robot origin is not.** `robot_geometry.py`'s `DEFAULT_WOBJ_ORIGIN` exists; the robot's own base position is separate geometry that hasn't been defined yet.
- **Very large or very distant geometry can get clipped** by the camera — a `compas_viewer` behavior, not a data problem. Check the Camera Settings dialog mentioned above.

## Related files

- `301_convert_to_compas_json.py` — converts raw sand-drawing data into COMPAS frames, calling `show_frames()` before and after.
- `302_process_toolpath.py` — applies offset and safe frames, calling `show_frames()` before and after.
- `robot_geometry.py` — provides `DEFAULT_WOBJ_ORIGIN`, shown in the viewer as the world origin marker.
- `README.md` — main repository documentation, including the full pipeline overview and safety checklist.
