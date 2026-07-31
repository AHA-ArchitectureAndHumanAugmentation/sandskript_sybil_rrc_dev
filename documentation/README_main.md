# main.py

The pipeline orchestrator. Runs `301_convert_to_compas_json.py`, then `302_process_toolpath.py`, in order, automatically handing each stage's output to the next one. Not a standalone tool with its own logic -- it just launches the other scripts, one after another, and stops if any of them fails.

## What it's for

Running `301` and `302` by hand means editing each script's own `INPUT_PATH` separately, and manually copying the right filename between them. `main.py` does this in one step: edit one line, press run, and the whole chain executes.

## Usage

```bash
python main.py
```

No arguments. Edit `INPUT_PATH` inside the file to select which capture from Lin goes through the pipeline:

```python
INPUT_PATH = ROOT / "data" / "in" / "2026-07-27_11-50-11" / "path.json"
```

## What it does, step by step

| Step | What happens |
|---|---|
| 1 | Reads `INPUT_PATH` -- the file you set at the top |
| 2 | Works out `BASE_NAME` -- a unique name for this run, used to predict every output filename downstream |
| 3 | Predicts `CONVERTED_PATH` and `PROCESSED_PATH` -- the exact filenames `301` and `302` are each about to produce |
| 4 | Runs `301_convert_to_compas_json.py` as a separate program, passing it `INPUT_PATH` |
| 5 | Runs `302_process_toolpath.py` as a separate program, passing it `CONVERTED_PATH` |
| 6 | `303_send_to_robot.py` is currently commented out -- skipped entirely (see "Known limitations" below) |

Each stage runs via `subprocess.run([...], check=True)` -- this launches the other script exactly as if you'd typed `python 301_convert_to_compas_json.py <file>` into a terminal yourself. `check=True` means: if a stage crashes, `main.py` stops immediately with an error, rather than continuing to the next stage with broken or missing data.

## The naming convention

Every one of Lin's captures is named `path.json` -- not unique on its own. `main.py` (and `301`, `302` independently) handle this the same way:

```python
BASE_NAME = INPUT_PATH.stem
if BASE_NAME == "path":
    BASE_NAME = INPUT_PATH.parent.name
```

If the filename is literally `"path"`, fall back to the **parent folder's name** instead (e.g. `"2026-07-27_11-50-11"`) -- that's where the real uniqueness lives. This is why `main.py` can correctly *predict* `301` and `302`'s output filenames before either one has run: all three scripts follow this exact same rule.

Resulting filenames:

| Stage | Output |
|---|---|
| `301` | `data/compas/<BASE_NAME>_compas.json` |
| `302` | `data/processed/<BASE_NAME>_processed.json` |

## Known limitations

- **`303_send_to_robot.py` is disabled.** The two lines that would run it are commented out in `main.py`. It needs Docker/ROS and the real robot connected, and there's a known issue where it would re-apply `TOOLPATH_OFFSET` and re-add safe frames on top of what `302` already did -- see the `KNOWN ISSUE` comment inside `303_send_to_robot.py`. To re-enable once resolved, remove the `#` from both lines at the bottom of `main.py`.
- **No error recovery.** If `301` fails partway through, `main.py` stops -- it doesn't retry or clean up any partial output.
- **Single file per run.** `main.py` processes exactly one capture at a time; it doesn't loop over every file in `data/in/` automatically. That's the job of the future MQTT bridge (not built yet -- see `TODO.md`).

## Related files

- `301_convert_to_compas_json.py` -- first stage, raw strokes to COMPAS frames
- `302_process_toolpath.py` -- second stage, offset and safe frames
- `303_send_to_robot.py` -- third stage, currently skipped
- `TODO.md` -- tracks what's still open, including the MQTT bridge this will eventually plug into
