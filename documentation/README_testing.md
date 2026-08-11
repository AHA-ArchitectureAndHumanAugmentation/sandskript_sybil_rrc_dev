# Testing Safely, Without a Robot

Everything in this pipeline can be exercised end-to-end — including the
full record → select → announce loop — without ever connecting to the real
robot. This is how.

## The safety flags, together

All in `304_send_to_robot.py`. Check these before running anything:

| Flag | Values | What it controls |
|---|---|---|
| `MODE` | `preview` / `execute` / `test_record` | Whether a robot connection is attempted **at all**. Only `execute` connects to ROS/ABB. |
| `ORIENTATION_MODE` | `radial` / `fixed` | Per-point orientation from the tween, vs. one orientation locked from HOME. Safe to switch either way — doesn't affect whether the robot moves. |
| `TEST_STEP` | `0`–`5` | Only relevant in `execute` mode. Staged checkpoints — work up incrementally, never jump straight to `5`. |
| `RECORD_IN_PREVIEW` | `True` / `False` | **Demo-only.** Makes preview mode also record a spray and run tile selection, so the loop can be shown live with zero robot risk. **Reset to `False` after any demo.** |

The only thing that can ever move the real robot is `MODE = "execute"`. Every
other flag is safe to leave in any state.

## Recommended order when testing something new

1. `MODE = "preview"` — confirm the geometry looks right in the viewer.
2. `MODE = "test_record"` — confirm recording, selection, and announcement
   all fire correctly, with zero robot connection.
3. Only once both of those look right: `MODE = "execute"`, starting at
   `TEST_STEP = 0` and working up one step at a time.

## 301b_flat_path_to_tile.py — synthetic test paths

Generates a fake capture without needing Rhino, Grasshopper, or Lin's real
pipeline running. Takes a flat 2D path (a plain JSON list of `[x, y]`
points) and projects it onto a real tile mesh via nearest-vertex matching:

```powershell
python 301b_flat_path_to_tile.py test_path.json --tile-id 2
```

Orientation from this tool is a placeholder — 302 rebuilds real orientation
from the sphere center regardless, so it doesn't matter that this tool's
orientation isn't geometrically meaningful.

## `data/executed/` vs. real evidence

Anything recorded while `RECORD_IN_PREVIEW = True` or via `test_record` mode
is **fake** — it looks identical to a real spray record in
`data/executed/`, because it's meant to exercise the exact same code path.
There is currently no flag distinguishing a demo record from a real one in
the saved files themselves — worth knowing before trusting tile eligibility
numbers after a demo session, and worth clearing `data/executed/` of
demo-only entries before they'd affect a real decision.

## `documentation/test_tile_do_not_delete/`

A preserved, known-good test capture — kept intentionally as a stable
fixture, not accumulated test junk. Leave it alone during any cleanup pass.

## Gotchas worth knowing before they cost you an hour

- **`git checkout` resets every file's modified-time**, even for files whose
  content didn't change. Anything that picks "the newest file" by
  modified-time can silently pick the wrong one after a branch switch.
  `main.py` and `300b_zmq_publisher.py` both sort `data/in` by the
  *timestamp in the folder name* specifically because of this.
- **A stale `__pycache__` can mask an unsaved edit.** If a change to a `.py`
  file doesn't seem to take effect, first confirm it's actually on disk
  (`Get-Content file.py | Select-String "the thing you added"`) before
  assuming it's a caching problem — an unsaved editor tab looks identical
  to a stale cache from the outside.
- **An open Word document can block a branch switch.** `git checkout` fails
  if a tracked file is open and locked elsewhere; close Office documents in
  the repo before switching branches.
