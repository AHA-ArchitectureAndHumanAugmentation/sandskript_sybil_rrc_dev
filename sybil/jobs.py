"""
Sybil — jobs, and remembering them.

WHAT THIS FILE IS FOR
A job is one visitor drawing, from the moment it is captured until every
layer has been sprayed and it has been watered.

The reason it exists: layer 1 happens live, while the visitor watches.
Layers 2, 3 and 4 happen in the maintenance window afterwards — up to
ninety minutes later. So the drawing has to survive on disk in between,
already projected, ready to replay without the camera or the tracking
process.

It also means the day survives a restart. Close the program at 13:00 and
reopen it, and the morning's drawings are still there waiting for their
remaining layers.

THREE KINDS OF WORK
    A_SUBSTRATE   visitor drawing, substrate, several layers, lane stepped
    A_WATER       that same drawing, water, once, from 700 mm
    B_WATER       a B tile's own pre-drawn path, water, once, from 700 mm

Lives in the RRC repo only:
    sandskript_sybil_rrc_dev/sybil/jobs.py
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from enum import Enum

from sybil import config


# ==========================================================================
# SETTINGS
# ==========================================================================

JOBS_DIR = config.REPO_ROOT / "data" / "jobs"
# Where the day's drawings are kept, in a folder per date. Each drawing is
# one .json file holding its projected frames and how many layers it has
# had so far.

KEEP_DAYS = 30
# How many days of job folders to keep. Older ones are deleted by
# tidy_up(). The surface is reset every night, so old jobs are only ever
# useful for looking back at what happened.
# Set to None to keep everything forever.

DEFAULT_LAYERS = 4
# How many layers a substrate job wants in total, including the live one.
# A water job always takes exactly one pass and ignores this.

# ==========================================================================


class JobKind(str, Enum):
    """What sort of work this is. Decides material, repeats and standoff."""
    A_SUBSTRATE = "a_substrate"   # visitor drawing, substrate, layered, lanes
    A_WATER = "a_water"           # visitor drawing, water, one pass, 700 mm
    B_WATER = "b_water"           # B tile's own path, water, one pass, 700 mm

    @property
    def is_water(self):
        return self is not JobKind.A_SUBSTRATE

    @property
    def uses_lanes(self):
        """Only substrate is lane stepped. Watering traces the line once."""
        return self is JobKind.A_SUBSTRATE

    @property
    def layer_count(self):
        return DEFAULT_LAYERS if self is JobKind.A_SUBSTRATE else 1


def new_job_id(window):
    """e.g. 20260907-w1-3f9c — date, window, short random tail."""
    return "{}-w{}-{}".format(
        datetime.now().strftime("%Y%m%d"), window, uuid.uuid4().hex[:4]
    )


def _now():
    return datetime.now().replace(microsecond=0).isoformat()


class Job:
    """One piece of work, and how far through it we are."""

    def __init__(self, job_id, tile_id, kind, frames,
                 window=None, created=None, source="drawn",
                 layers_done=0, layer_times=None, watered=False,
                 deferred=None, aborts=None):
        self.job_id = job_id
        self.tile_id = tile_id
        self.kind = JobKind(kind)
        self.frames = frames          # already projected, robot coordinates
        self.window = window
        self.created = created or _now()
        self.source = source          # "drawn", "repertoire", "tile_path"
        self.layers_done = layers_done
        self.layer_times = layer_times or []
        self.watered = watered
        self.deferred = deferred or []
        self.aborts = aborts or []

    # -- what is left to do -----------------------------------------------

    @property
    def layers_wanted(self):
        return self.kind.layer_count

    @property
    def layers_left(self):
        return max(0, self.layers_wanted - self.layers_done)

    @property
    def next_layer(self):
        """Which layer number to spray next. None when there are none left."""
        return self.layers_done + 1 if self.layers_left else None

    @property
    def needs_water(self):
        """Whether this job still wants its watering pass.

        NOT gated on layers being finished. Under plan B, layer 4 is
        deferred to a later window but watering still happens at the end of
        this one — the seedlings do not wait for the schedule.
        """
        return not self.watered

    @property
    def is_finished(self):
        return self.layers_left == 0 and self.watered

    # -- recording what happened ------------------------------------------

    def record_layer(self, layer=None, duration_s=None):
        """A layer was sprayed. Clears it from the deferred list if it was
        waiting there, so a picked-up backlog does not stay in the backlog."""
        self.layers_done = layer if layer is not None else self.layers_done + 1
        self.layer_times.append(_now())
        if self.layers_done in self.deferred:
            self.deferred.remove(self.layers_done)
        return self

    def record_water(self):
        """The watering pass ran.

        For a water job this IS the work, so it counts as its one pass too.
        Otherwise the job would sit at 0 layers done forever and never look
        finished.
        """
        self.watered = True
        if self.kind.is_water and self.layers_done < self.layers_wanted:
            self.layers_done = self.layers_wanted
            self.layer_times.append(_now())
        return self

    def record_abort(self, reason, layer=None):
        self.aborts.append({"when": _now(), "reason": str(reason), "layer": layer})
        return self

    def record_deferred(self, layer):
        if layer not in self.deferred:
            self.deferred.append(layer)
        return self

    # -- disk -------------------------------------------------------------

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "tile_id": self.tile_id,
            "kind": self.kind.value,
            "window": self.window,
            "created": self.created,
            "source": self.source,
            "layers_done": self.layers_done,
            "layers_wanted": self.layers_wanted,
            "layer_times": self.layer_times,
            "watered": self.watered,
            "deferred": self.deferred,
            "aborts": self.aborts,
            "frames": self.frames,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            job_id=data["job_id"],
            tile_id=data["tile_id"],
            kind=data["kind"],
            frames=data.get("frames", []),
            window=data.get("window"),
            created=data.get("created"),
            source=data.get("source", "drawn"),
            layers_done=data.get("layers_done", 0),
            layer_times=data.get("layer_times"),
            watered=data.get("watered", False),
            deferred=data.get("deferred"),
            aborts=data.get("aborts"),
        )

    def __repr__(self):
        return "Job({} tile {} {} {}/{} layers{})".format(
            self.job_id, self.tile_id, self.kind.value,
            self.layers_done, self.layers_wanted,
            " watered" if self.watered else "")


class JobStore:
    """The day's jobs on disk, one folder per date."""

    def __init__(self, day=None, root=None):
        self.root = JOBS_DIR if root is None else root
        self.day = day or datetime.now().strftime("%Y%m%d")
        self.folder = self.root / self.day
        self.folder.mkdir(parents=True, exist_ok=True)

    def path_for(self, job_id):
        return self.folder / "{}.json".format(job_id)

    # -- writing ----------------------------------------------------------

    def save(self, job):
        """Write a job, replacing whatever was there.

        Written to a temporary file first, then moved into place, so a crash
        mid-write cannot leave a half-written job that fails to load later.
        """
        target = self.path_for(job.job_id)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
        temporary.replace(target)
        return target

    # -- reading ----------------------------------------------------------

    def load(self, job_id):
        path = self.path_for(job_id)
        if not path.exists():
            return None
        return Job.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def all(self):
        """Every job today, oldest first."""
        jobs = []
        for path in sorted(self.folder.glob("*.json")):
            try:
                jobs.append(Job.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (ValueError, KeyError) as error:
                print("Could not read {}: {}".format(path.name, error))
        return sorted(jobs, key=lambda j: j.created)

    def for_window(self, window):
        return [j for j in self.all() if j.window == window]

    def needing_layers(self, window=None):
        """Jobs with layers still to spray. Used by maintenance."""
        jobs = self.for_window(window) if window is not None else self.all()
        return [j for j in jobs if j.layers_left > 0]

    def needing_water(self, window=None):
        jobs = self.for_window(window) if window is not None else self.all()
        return [j for j in jobs if j.needs_water]

    def deferred(self):
        """Jobs from earlier windows that were left unfinished. Maintenance
        window 4 picks these up, oldest first."""
        return [j for j in self.all() if j.deferred and j.layers_left > 0]

    # -- housekeeping -----------------------------------------------------

    def tidy_up(self, keep_days=None):
        """Delete job folders older than KEEP_DAYS."""
        keep_days = KEEP_DAYS if keep_days is None else keep_days
        if keep_days is None:
            return []

        cutoff = datetime.now().timestamp() - keep_days * 86400
        removed = []
        for folder in self.root.iterdir():
            if not folder.is_dir() or folder == self.folder:
                continue
            if folder.stat().st_mtime < cutoff:
                for item in folder.iterdir():
                    item.unlink()
                folder.rmdir()
                removed.append(folder.name)
        return removed

    # -- reporting --------------------------------------------------------

    def summary(self):
        jobs = self.all()
        print("Jobs for {} — {} total".format(self.day, len(jobs)))
        if not jobs:
            return

        for window in sorted(set(j.window for j in jobs if j.window is not None)):
            in_window = [j for j in jobs if j.window == window]
            done = sum(1 for j in in_window if j.is_finished)
            print("  window {}: {} jobs, {} finished".format(window, len(in_window), done))

        outstanding = [j for j in jobs if not j.is_finished]
        if outstanding:
            print("  {} unfinished:".format(len(outstanding)))
            for job in outstanding:
                note = []
                if job.layers_left:
                    note.append("{} layer(s) left".format(job.layers_left))
                if job.needs_water:
                    note.append("needs water")
                if job.deferred:
                    note.append("deferred {}".format(job.deferred))
                print("    {} — {}".format(job.job_id, ", ".join(note)))


# --------------------------------------------------------------------------
# Check: python -m sybil.jobs
#
# Runs a fake interaction window and the maintenance window after it,
# including a job that gets its layer 4 deferred.
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import shutil

    test_root = config.REPO_ROOT / "data" / "jobs_test"
    if test_root.exists():
        shutil.rmtree(test_root)

    store = JobStore(day="test", root=test_root)
    frames = [[x, 1000, 900, 1, 0, 0, 0] for x in range(0, 1600, 100)]

    print("--- interaction window 1: four visitors draw ---")
    for i in range(4):
        job = Job(new_job_id(1), "tile_A_00{}".format(i + 1),
                  JobKind.A_SUBSTRATE, frames, window=1)
        job.record_layer(1)
        store.save(job)
        print("  {} sprayed layer 1".format(job.job_id))

    print("\n--- maintenance window 1: layers 2 and 3 ---")
    for layer in (2, 3):
        for job in store.needing_layers(window=1):
            job.record_layer(layer)
            store.save(job)
        print("  all jobs at layer {}".format(layer))

    print("\n--- time runs short: layer 4 deferred ---")
    for job in store.needing_layers(window=1):
        job.record_deferred(4)
        store.save(job)
    print("  {} job(s) deferred".format(len(store.deferred())))

    print("\n--- watering (happens even though layer 4 was deferred) ---")
    watered = 0
    for job in store.needing_water(window=1):
        job.record_water()
        store.save(job)
        watered += 1
    print("  {} job(s) watered".format(watered))
    assert watered == 4, "watering must not wait for deferred layers"

    print("\n--- B tile watering ---")
    b_job = Job(new_job_id(1), "tile_B_002", JobKind.B_WATER, frames,
                window=1, source="tile_path")
    b_job.record_water()
    store.save(b_job)
    print("  {} — finished: {}".format(b_job.job_id, b_job.is_finished))

    print("\n--- maintenance window 4 picks up the backlog ---")
    for job in store.deferred():
        job.record_layer(4)
        store.save(job)
    print("  {} job(s) still deferred".format(len(store.deferred())))

    print()
    store.summary()

    print("\n--- surviving a restart ---")
    reopened = JobStore(day="test", root=test_root)
    print("  reloaded {} jobs from disk".format(len(reopened.all())))
    assert len(reopened.all()) == 5
    assert all(j.is_finished for j in reopened.all())
    print("  all finished, nothing lost")

    shutil.rmtree(test_root)
    print("\njobs ok")
