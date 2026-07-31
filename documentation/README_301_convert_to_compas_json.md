# 301_convert_to_compas_json.py

Converts a raw drawing toolpath (strokes + planes) into COMPAS frames. If the input file is already in converted format, it's just shown as-is -- no conversion needed. Shows a before/after comparison in `compas_viewer`.

## What it's for

Lin's system sends raw stroke data -- multiple strokes, each a list of points, each point carrying its own plane. This script is the first stage in the pipeline: it flattens that structure into COMPAS `Frame` objects and scales the coordinates from metres to millimetres.

## Usage

```bash
python 301_convert_to_compas_json.py
python 301_convert_to_compas_json.py data/in/2026-07-27_11-50-11/path.json
```

No argument defaults to `DEFAULT_INPUT_PATH` (`data/in/path.json`). Called automatically by `main.py` as the first pipeline stage.

## What it does

| Step | What happens |
|---|---|
| 1 | Loads the input file |
| 2 | Checks whether it has `"strokes"` (raw) or `"frames"` (already converted) |
| 3a | If raw: converts every stroke's points into COMPAS frames, scaling by `COORDINATE_SCALE` |
| 3b | If already converted: skips conversion entirely |
| 4 | Saves the result to `data/compas/<name>_compas.json` |
| 5 | Shows a `compas_viewer` window: raw input (light gray) next to converted output (dark) -- or the same data twice, if no conversion was needed |

## Constants

| Constant | Value | Purpose |
|---|---|---|
| `COORDINATE_SCALE` | `1000.0` | Metres -> millimetres. Comment/uncomment the two lines in the file to switch to `1.0` once Lin sends millimetres directly |

## The naming convention

Every one of Lin's captures is named `path.json` -- not unique on its own. This script (and `main.py`) handle this the same way:

```python
BASE_NAME = INPUT_PATH.stem
if BASE_NAME == "path":
    BASE_NAME = INPUT_PATH.parent.name
```

If the filename is literally `"path"`, the **parent folder's name** is used instead (e.g. `"2026-07-27_11-50-11"`) -- that's where the real uniqueness lives.

## Known considerations

- **Scale must not be changed beyond the metres -> millimetres conversion.** See `TODO.md` -- the path must stay recoverable back to its original tile position, so no other distortion should be introduced here.
- **`wobj_origin`/`wobj_xaxis`/`wobj_yaxis`** get written into the output using `robot_geometry.py`'s `DEFAULT_WOBJ_ORIGIN/XAXIS/YAXIS` -- only present in files that went through real conversion (step 3a), not in already-converted pass-through files.

## Related files

- `robot_geometry.py` -- provides the `DEFAULT_WOBJ_ORIGIN/XAXIS/YAXIS` values written into converted output
- `view_utils.py` -- provides `show_comparison()`, used for the before/after viewer
- `302_process_toolpath.py` -- consumes this script's output
- `main.py` -- runs this script as the first pipeline stage
- `TODO.md` -- tracks the origin/scale-preservation requirements
