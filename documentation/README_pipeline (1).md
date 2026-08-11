# The Pipeline: 301 → 302 → 304

The core chain that turns a captured drawing into an actual (or previewed)
robot spray path. Every stage reads one JSON file and writes another —
nothing is held in memory between stages, so any stage can be re-run on its
own against a saved file.

```text
data/in/<timestamp>/path.json
        ↓  301_convert_to_compas_json.py
data/compas/<name>_compas.json
        ↓  302_process_toolpath.py
data/processed/<name>_processed.json
        ↓  304_send_to_robot.py
   preview window   OR   real robot execution
        ↓  (only on a real, complete spray)
data/executed/<timestamp>_tile<N>_<type>.json
```

## 1. 301_convert_to_compas_json.py

Reads the raw capture (Lin's format: a list of "strokes," each a list of
`{"plane": {"origin", "xaxis", "yaxis"}}`), converts every point into a
proper COMPAS `Frame`, and writes it to `data/compas/`.

| Setting | Value | Purpose |
|---|---|---|
| `COORDINATE_SCALE` | `1.0` | No scaling applied — confirmed Lin's pipeline outputs millimetres natively |

If a future data source turns out to be in metres, this is the one place to
change it — do not add scaling anywhere downstream.

`tile_id`, if present in the source file, is carried through untouched. If
absent, it stays `None` all the way down the chain, and 304 will skip spray
recording rather than guess.

## 2. 302_process_toolpath.py

Reads the converted frames, morphs the path, and writes the robot-ready
version.

**`RadialShell`** — a center + radius, used purely as a math helper for two
things: projecting a point onto a shell's surface, and clamping a point
that has drifted outside a shell back onto it.

**`ToolpathMorph`** — the actual pipeline step. For every point:

1. Projects it onto a shell at `TARGET_RADIUS` from the shared center — this is "curve B."
2. Blends between the original point ("curve A") and curve B by `T`.
3. Clamps the blended point to `SAFETY_RADIUS` — a hard ceiling no point may ever exceed.
4. Rebuilds the frame's orientation radially, pointing outward from the shared center.

| Setting | Meaning |
|---|---|
| `TARGET_RADIUS` | Radius the toolpath lands on when `T = 1.0` |
| `T` | Blend factor: `0.0` = untouched original, `1.0` = fully on the target shell |
| `SPHERE_CENTER`, `SAFETY_RADIUS` | Imported from `fixed_geometry.py`, not defined here |

> **Why safe frames aren't added here:** they used to be, and 304 also
> added its own — every spray got a doubled, over-lifted approach point.
> Safe frames are 304's responsibility alone now, computed there from the
> robot's live measured orientation, which 302 has no way to know in
> advance.

## 3. fixed_geometry.py

The single source of truth for anything physically fixed about the
installation. Everything else imports from here rather than redefining its
own copy — that duplication caused a real alignment bug earlier.

| Constant | What it is |
|---|---|
| `WORLD_ORIGIN` | The robot's base, the world object's origin, and the safety sphere's center — all the same literal point, not three values that happen to match |
| `SPHERE_CENTER` | References `WORLD_ORIGIN` directly |
| `SAFETY_RADIUS` | Hard reach limit — no point, from any script, at any stage, may exceed this distance from `WORLD_ORIGIN` |

## 4. view_utils.py — `show_comparison(...)`

Opens a `compas_viewer` window and **blocks** — nothing continues until
it's closed. Called automatically at the end of 301, 302, and 304 (in
preview mode). Draws:

- The "before" and "after" polylines
- The target and safety shells, if radii are passed in
- Per-frame X/Y/Z axis triads (toggle with `SHOW_NORMALS`)
- The physical spray surface mesh, if `sybil_geo/surface.obj` exists
- Start/end/world-origin markers

Camera framing, axis/point sizing, and colors are all pulled into constants
at the top of the file. If the geometry ever looks "microscopic" again:
check the camera framing math before assuming it's a units problem — it
usually isn't; the geometry itself has consistently been correct
millimetres.

## 5. 304_send_to_robot.py

Reads the processed file and either shows it or runs it for real, depending
on `MODE`.

| MODE | What happens |
|---|---|
| `"preview"` | Opens the checkpoint viewer. No robot connection at all. |
| `"execute"` | Connects to ROS/ABB, runs the staged `TEST_STEP`. |
| `"test_record"` | Simulates a successful spray — runs recording/selection/announcement with no robot connection. |

| Other setting | Purpose |
|---|---|
| `ORIENTATION_MODE` | `"radial"` = per-point orientation from the tween (matches preview). `"fixed"` = locks every frame to the orientation measured live at `HOME_CONFIG`. |
| `TEST_STEP` (0–5) | Staged execution checkpoints. Work up incrementally before ever running step 5 for real. |
| `RECORD_IN_PREVIEW` | Demo-only. When `True`, preview mode also records a spray and runs tile selection. **Reset to `False` after any demo.** |

Safe frames retreat toward `SPHERE_CENTER`, not straight up — computed
fresh from each point's position, correct regardless of orientation.

`HOME_CONFIG`, `TOOL_NAME`, and `WORK_OBJECT` are calibrated to the real
robot — never revert these to older reference values.

## 6. pipeline_utils.py

The shared `run_pipeline()` function — the *only* place the
301 → 302 → 304 sequence is defined. `main.py`, `300_watch_and_run.py`, and
the ZeroMQ listener all call this instead of reimplementing it, so they
can't drift out of sync with each other again.

## 7. main.py

Thin entry point. `RUN_MODE`:

| Mode | Behavior |
|---|---|
| `"single"` | Process one capture and exit. Auto-picks the newest *timestamped folder name* in `data/in` — not modified-time, since a git checkout resets that even when content hasn't changed. |
| `"autonomous"` | See README_messaging.md. |
