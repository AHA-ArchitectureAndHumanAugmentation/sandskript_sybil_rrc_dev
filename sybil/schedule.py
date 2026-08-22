"""
Sybil — the exhibition clock.

WHAT THIS FILE IS FOR
Knows what time it is and what the robot should be doing:

    which window is open right now
    how many visitors have drawn in it
    when to stop accepting drawings and start maintenance
    whether there is time for layer 4 or only layers 2 and 3

Nothing here touches the robot, the net, or any geometry. It is pure
timekeeping, so a whole exhibition day can be simulated in under a minute.

THE SHAPE OF A DAY
    before 10:00    water every tile, one path each
    10:00–10:30     visitors draw, robot sprays layer 1 immediately
    10:30–12:00     no visitors. Layers 2, 3, 4, then watering
    ... repeated four times ...
    16:30 onward    last maintenance, plus anything deferred earlier
    after that      water every tile again

Lives in the RRC repo only:
    sandskript_sybil_rrc_dev/sybil/schedule.py
"""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, time, timedelta
from enum import Enum

from sybil import config


# ==========================================================================
# SETTINGS
# ==========================================================================

# --- Window times --------------------------------------------------------
#
# Each pair is (interaction start, maintenance start). Interaction runs from
# the first to the second; maintenance runs from the second until the next
# interaction begins.
#
# Interaction windows are HARD EDGED — they start and end on the clock, no
# matter what. All the slack in the day lives in maintenance.

WINDOWS = [
    (time(10, 0), time(10, 30)),
    (time(12, 0), time(12, 30)),
    (time(14, 0), time(14, 30)),
    (time(16, 0), time(16, 30)),
]
# Add or remove a pair to change how many windows the day has.
# Move a time and everything downstream shifts with it.

DAY_START = time(9, 0)
# When the morning watering rotation begins. Must leave enough time to get
# round every tile before the first interaction window opens.

DAY_END = time(18, 0)
# Hard stop. Maintenance window 4 finishes here whatever is left undone,
# and the evening watering runs after it.
# Set to None to let the last window run until the work is finished — every
# layer gets applied, but nobody knows when they are going home.

# --- What kind of day is it ---------------------------------------------

DAY_MODE = "substrate"
# Set this each morning, before starting the day. Two values:
#
#   "substrate"   The normal day. A visitor's drawing is sprayed with
#                 substrate — four lanes, then three more layers in the
#                 maintenance window afterwards, then watered.
#
#   "water"       A rest day for the surface. Visitors still draw, and the
#                 robot still traces their line, but with water: one pass,
#                 no lane stepping, no later layers. The mark shows as a wet
#                 line and fades. B tiles are watered as usual.
#
# Nothing else changes — the windows, the caps and the interaction all work
# the same way. Only what comes out of the nozzle, and how many times.

# --- What to do when there is nothing to do ------------------------------
#
# A still robot reads as a broken robot. Between drawings, and through the
# quiet stretches of a maintenance window, the arm can keep working.

IDLE_ACTION = "water"
# "none"       Sit at home. Honest, but the piece looks dead to anyone
#              watching.
# "water"      Water whichever tile has gone longest without it. Safe, and
#              the tiles can take it.
# "substrate"  Spray substrate on a due A tile, from the watering standoff
#              so it lands as a mist rather than a line. Keeps the arm
#              moving AND builds the surface up.
#              Ignored on a water day — that day exists to rest the surface,
#              so idle substrate would defeat the point.

IDLE_TIMEOUT_S = 150.0
# How long the robot sits at home before IDLE_ACTION starts.
# Shorter = livelier, more material and water used.
# Longer = calmer, but longer dead stretches while visitors watch.

IDLE_SUBSTRATE_CAP_PER_TILE = 2
# How many idle substrate passes any one A tile may receive per day, on top
# of the visitor drawings it already carries.
# Stops a quiet afternoon from soaking a single tile.

# --- Capacity ------------------------------------------------------------

INTERACTIONS_PER_WINDOW = 4
# How many visitors may draw in one interaction window.
# Raise it and more people get to draw, but each has less time and the
# maintenance window afterwards has more work to fit in.
# Lower it for a calmer day with more slack.
# At 4, a full day is 16 drawings and 64 spray toolpaths.

LAYERS_PER_JOB = 4
# How many times each drawing is sprayed in total.
# Layer 1 happens live while the visitor watches. Layers 2, 3 and 4 happen
# in the maintenance window afterwards, with drying time between them.
# Fewer layers = a thinner mark and a much shorter day.

# --- Fitting the work into the time --------------------------------------

# --- How long things take ------------------------------------------------
#
# The schedule has to decide whether layer 4 will fit before a maintenance
# window closes. That needs a number: how long does one spray take?
#
# Rather than tuning a constant by hand, the executor reports each finished
# toolpath and the average is used from then on. The two fallbacks below are
# only for the first few toolpaths of the first day.
#
# You should not need to touch these. If you change TOOLPATH_SPEED or
# LANE_COUNT, delete data/timings.json instead — the old measurements no
# longer describe the new setup.

ESTIMATED_CYCLE_S = 340.0
# Assumed seconds for one substrate spray, home to home, before any have
# been measured.

ESTIMATED_WATER_S = 200.0
# Assumed seconds for one watering pass, before any have been measured.

USE_MEASURED_TIMINGS = True
# True  = use real measured numbers once enough toolpaths have run.
# False = always use the two fallbacks above. Useful for testing the
#         schedule on its own, with predictable arithmetic.

FALLBACK_SPRAY_S = 340.0
# What to assume for a substrate spray before any have been measured.
# Only used for the first few toolpaths of the first day. After that, real
# measurements take over. Rough is fine.

FALLBACK_WATER_S = 200.0
# The same, for a watering pass. Shorter: faster movement, no lane stepping.

SAMPLE_SIZE = 8
# How many recent toolpaths to average over.
# Small (3-5) = follows changes quickly, e.g. after you change the speed
#               mid-day, but a single odd run swings the estimate.
# Large (15+) = steadier, slower to notice a change.
# Eight covers about two maintenance windows.

MIN_SAMPLES = 2
# How many real measurements are needed before the fallback is dropped.
# One measurement could be a fluke — an E-stop, or a path that aborted
# early — so wait for a second before trusting it.

OUTLIER_FACTOR = 3.0
# Ignore any toolpath that took more than this many times the current
# average. Catches a run that was paused, or one that sat waiting for
# someone to clear the cell. Set to 0 to keep everything.

TIMINGS_FILE = config.REPO_ROOT / "data" / "timings.json"
# Where measurements are saved, so a restart mid-day does not go back to
# guessing. Delete this file to start fresh — worth doing after changing
# TOOLPATH_SPEED or LANE_COUNT, since old timings no longer apply.

SAVE_EVERY = 1
# How often to write the file. 1 = after every toolpath, which is safest.
# Raise it if the disk writes ever become a nuisance.

TIME_SAFETY_MARGIN = 1.15
# How much slack to leave when deciding if work will fit.
# 1.15 means "assume everything takes 15% longer than estimated".
# Higher = drops layer 4 more readily, finishes on time more reliably.
# 1.0 = trust the estimate exactly, and overrun whenever it is optimistic.

# ==========================================================================


class Phase(str, Enum):
    """What part of the day it is."""
    CLOSED = "closed"              # before DAY_START or after everything
    MORNING_WATER = "morning_water"  # rotation before doors open
    INTERACTION = "interaction"    # visitors may draw
    MAINTENANCE = "maintenance"    # layers 2-4 and watering, no visitors
    EVENING_WATER = "evening_water"  # rotation after the last maintenance


class DayMode(str, Enum):
    """What the robot sprays today. Set by DAY_MODE above, each morning."""
    SUBSTRATE = "substrate"    # the normal day
    WATER_ONLY = "water"       # a rest day for the surface

    @property
    def live_material(self):
        """What layer 1 is sprayed with while the visitor watches."""
        return "substrate" if self is DayMode.SUBSTRATE else "water"

    @property
    def uses_lanes(self):
        """Substrate is stepped into lanes to widen the mark. Water is not —
        it traces the line once."""
        return self is DayMode.SUBSTRATE

    @property
    def later_layers(self):
        """Which layers happen in the maintenance window afterwards.
        A water-only day has none: the drawing was finished live."""
        return (2, 3, 4) if self is DayMode.SUBSTRATE else ()

    @property
    def waters_a_tiles(self):
        """Substrate days water the A tiles in maintenance, after the last
        layer. Water-only days already did it, live."""
        return self is DayMode.SUBSTRATE


# --------------------------------------------------------------------------
# Measured timings
#
# Remembers how long toolpaths actually take, so the planning above stops
# guessing. The executor reports each finished toolpath here.
# --------------------------------------------------------------------------

SPRAY = "spray"
WATER = "water"


class Timings:
    """Recent durations, per kind of work."""

    def __init__(self, path=None):
        self.path = TIMINGS_FILE if path is None else path
        self.samples = {SPRAY: deque(maxlen=SAMPLE_SIZE),
                        WATER: deque(maxlen=SAMPLE_SIZE)}
        self.totals = {SPRAY: 0, WATER: 0}     # lifetime counts, for the log
        self.rejected = {SPRAY: 0, WATER: 0}
        self._since_save = 0
        self.load()

    # -- recording --------------------------------------------------------

    def record(self, kind, seconds, aborted=False):
        """Report a finished toolpath.

        Aborted runs are not recorded — a job that stopped after two frames
        would drag the average down and make the schedule over-confident.
        """
        if kind not in self.samples:
            raise ValueError("Unknown kind of work: {!r}".format(kind))

        if aborted or seconds <= 0:
            return

        if OUTLIER_FACTOR and self.samples[kind]:
            current = self.estimate(kind)
            if seconds > current * OUTLIER_FACTOR:
                self.rejected[kind] += 1
                print("  [timing] ignoring {:.0f} s {} — {:.1f}x the average".format(
                    seconds, kind, seconds / current))
                return

        self.samples[kind].append(float(seconds))
        self.totals[kind] += 1

        self._since_save += 1
        if self._since_save >= SAVE_EVERY:
            self.save()

    # -- asking -----------------------------------------------------------

    def estimate(self, kind):
        """Best guess at how long one of these takes, in seconds."""
        samples = self.samples.get(kind)
        if not samples or len(samples) < MIN_SAMPLES:
            return FALLBACK_SPRAY_S if kind == SPRAY else FALLBACK_WATER_S
        return sum(samples) / len(samples)

    @property
    def spray_s(self):
        return self.estimate(SPRAY)

    @property
    def water_s(self):
        return self.estimate(WATER)

    def is_measured(self, kind):
        """False while still using the fallback."""
        return len(self.samples.get(kind, ())) >= MIN_SAMPLES

    # -- saving -----------------------------------------------------------

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated": datetime.now().isoformat(timespec="seconds"),
            "samples": {k: list(v) for k, v in self.samples.items()},
            "totals": self.totals,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._since_save = 0

    def load(self):
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            print("  [timing] could not read {}: {}".format(self.path, error))
            return

        for kind, values in payload.get("samples", {}).items():
            if kind in self.samples:
                self.samples[kind] = deque(values, maxlen=SAMPLE_SIZE)
        self.totals.update(payload.get("totals", {}))

    def reset(self):
        """Throw away everything. Do this after changing TOOLPATH_SPEED or
        LANE_COUNT — old timings no longer describe the new setup."""
        for kind in self.samples:
            self.samples[kind].clear()
            self.totals[kind] = 0
            self.rejected[kind] = 0
        self.save()

    # -- reporting --------------------------------------------------------

    def describe(self):
        print("Timings ({})".format(self.path))
        for kind in (SPRAY, WATER):
            samples = self.samples[kind]
            source = "measured" if self.is_measured(kind) else "FALLBACK"
            print("  {:<6} {:>6.0f} s   {}  ({} sample(s), {} total, {} ignored)".format(
                kind, self.estimate(kind), source,
                len(samples), self.totals[kind], self.rejected[kind]))


_timings = None


def timings():
    """The shared timings, loaded on first use."""
    global _timings
    if _timings is None:
        _timings = Timings()
    return _timings

def set_timings(instance):
    """Replace the shared timings. Used by tests, and to point at a
    different file without restarting."""
    global _timings
    _timings = instance



def current_estimates():
    """The seconds-per-toolpath numbers to plan with.

    Real measurements once enough toolpaths have run, the fallbacks above
    until then. Returns (spray_seconds, water_seconds).
    """
    if not USE_MEASURED_TIMINGS:
        return ESTIMATED_CYCLE_S, ESTIMATED_WATER_S
    measured = timings()
    return measured.spray_s, measured.water_s


def idle_action_for(day_mode):
    """What IDLE_ACTION actually means today.

    Substrate is never sprayed on a water day, whatever the setting says —
    that day exists to rest the surface.
    """
    action = str(IDLE_ACTION).lower()
    if action == "substrate" and DayMode(day_mode) is not DayMode.SUBSTRATE:
        return "water"
    return action


class Plan(str, Enum):
    """How much of a maintenance window's work will fit."""
    FULL = "full"      # layers 2, 3, 4, then watering
    SHORT = "short"    # layers 2, 3, then watering. Layer 4 deferred.

    @property
    def layers(self):
        return (2, 3, 4) if self is Plan.FULL else (2, 3)


def _at(day, t):
    """A time of day, on a particular date."""
    return datetime.combine(day.date(), t)


class Schedule:
    """The day's timetable. Ask it what should be happening.

    Every method takes a `now` so a whole day can be replayed quickly in
    testing. Leave it out and it uses the real clock.
    """

    def __init__(self, windows=None, day_start=None, day_end=None,
                 interactions_per_window=None, day_mode=None):
        self.windows = WINDOWS if windows is None else windows
        self.day_start = DAY_START if day_start is None else day_start
        self.day_end = DAY_END if day_end is None else day_end
        self.cap = (INTERACTIONS_PER_WINDOW if interactions_per_window is None
                    else interactions_per_window)
        self.day_mode = DayMode(DAY_MODE if day_mode is None else day_mode)

    # -- where are we -----------------------------------------------------

    def phase(self, now=None):
        """What the robot should be doing right now."""
        now = now or datetime.now()
        t = now.time()

        if self.day_end is not None and t >= self.day_end:
            return Phase.CLOSED
        if t < self.day_start:
            return Phase.CLOSED

        first_interaction = self.windows[0][0]
        if t < first_interaction:
            return Phase.MORNING_WATER

        for index, (start, maintenance_start) in enumerate(self.windows):
            if start <= t < maintenance_start:
                return Phase.INTERACTION
            window_end = self._window_end(index)
            if maintenance_start <= t < window_end:
                return Phase.MAINTENANCE

        return Phase.EVENING_WATER

    def window_number(self, now=None):
        """Which window we are in or have just left. 1-based. None before
        the first one opens."""
        now = now or datetime.now()
        t = now.time()

        if t < self.windows[0][0]:
            return None

        for index in range(len(self.windows)):
            if t < self._window_end(index):
                return index + 1

        return len(self.windows)

    def _window_end(self, index):
        """When window `index`'s maintenance finishes: the next interaction
        window opening, or the hard stop for the last one."""
        if index + 1 < len(self.windows):
            return self.windows[index + 1][0]
        return self.day_end if self.day_end is not None else time(23, 59)

    # -- boundaries -------------------------------------------------------

    def phase_ends_at(self, now=None):
        """When the current phase finishes."""
        now = now or datetime.now()
        t = now.time()
        phase = self.phase(now)

        if phase is Phase.MORNING_WATER:
            return _at(now, self.windows[0][0])

        if phase is Phase.INTERACTION:
            for start, maintenance_start in self.windows:
                if start <= t < maintenance_start:
                    return _at(now, maintenance_start)

        if phase is Phase.MAINTENANCE:
            index = self.window_number(now) - 1
            return _at(now, self._window_end(index))

        if phase is Phase.EVENING_WATER and self.day_end is not None:
            return _at(now, self.day_end)

        return _at(now, time(23, 59))

    def seconds_left_in_phase(self, now=None):
        now = now or datetime.now()
        return max(0.0, (self.phase_ends_at(now) - now).total_seconds())

    # -- deciding how much work fits --------------------------------------

    def maintenance_work(self, job_count, b_tile_count, plan=None):
        """What a maintenance window has to get through.

        Three different things happen in one, and they are not the same
        length:

            A layers    the drawings from the window before, sprayed again
            A watering  those same drawings, traced with water at 700 mm
            B watering  each B tile's own path, once

        On a water-only day the A drawings were finished live, so only the
        B tiles remain.

        Returns (spray_count, water_count, seconds).
        """
        plan = Plan.FULL if plan is None else plan

        if self.day_mode is DayMode.SUBSTRATE:
            layers = [n for n in plan.layers]
            sprays = job_count * len(layers)
            waters = job_count + b_tile_count
        else:
            sprays = 0
            waters = b_tile_count

        spray_s, water_s = current_estimates()
        seconds = sprays * spray_s + waters * water_s
        return sprays, waters, seconds

    def plan_for(self, job_count, b_tile_count=0, now=None):
        """Full or short plan for this maintenance window?

        Checked when the window starts, and again after layer 3 finishes,
        using real elapsed time rather than the estimate made earlier.

        Layer 4 is all jobs or none. Applying it to some and not others
        would leave marks on one tile visibly denser than their neighbours,
        which reads as a mistake rather than variation.

        On a water-only day there are no later layers at all, so the answer
        is always SHORT.
        """
        if self.day_mode is not DayMode.SUBSTRATE or job_count <= 0:
            return Plan.SHORT

        remaining = self.seconds_left_in_phase(now)
        _, _, needed = self.maintenance_work(job_count, b_tile_count, Plan.FULL)

        return Plan.FULL if remaining >= needed * TIME_SAFETY_MARGIN else Plan.SHORT

    def fits(self, seconds, now=None):
        """Is there time for one more piece of work before the phase ends?"""
        return self.seconds_left_in_phase(now) >= seconds * TIME_SAFETY_MARGIN

    # -- reporting --------------------------------------------------------

    def describe(self):
        print("Exhibition day — {} day".format(self.day_mode.value))
        print("  {} watering rotation".format(self.day_start.strftime("%H:%M")))
        for index, (start, maintenance_start) in enumerate(self.windows):
            end = self._window_end(index)
            print("  {}-{}  interaction {}   max {} visitors".format(
                start.strftime("%H:%M"), maintenance_start.strftime("%H:%M"),
                index + 1, self.cap))
            print("  {}-{}  maintenance {}".format(
                maintenance_start.strftime("%H:%M"), end.strftime("%H:%M"),
                index + 1))
        if self.day_end is not None:
            print("  {} hard stop".format(self.day_end.strftime("%H:%M")))
        else:
            print("  no hard stop — runs until the work is done")

        total_drawings = len(self.windows) * self.cap
        if self.day_mode is DayMode.SUBSTRATE:
            print("\n  {} drawings/day, {} substrate sprays, {} A waterings".format(
                total_drawings, total_drawings * LAYERS_PER_JOB, total_drawings))
        else:
            print("\n  {} drawings/day, all traced with water, one pass each".format(
                total_drawings))
            print("  no later layers — maintenance windows only water the B tiles")


class WindowState:
    """How the current interaction window is going.

    Counts drawings so the cap can be enforced, and resets itself when the
    window number changes.
    """

    def __init__(self, cap=None):
        self.cap = INTERACTIONS_PER_WINDOW if cap is None else cap
        self.window = None
        self.used = 0
        self.jobs = []

    def sync(self, window_number):
        """Call whenever the window might have changed. Returns True if a
        new window just started."""
        if window_number != self.window:
            self.window = window_number
            self.used = 0
            self.jobs = []
            return True
        return False

    @property
    def is_full(self):
        return self.used >= self.cap

    @property
    def remaining(self):
        return max(0, self.cap - self.used)

    def record(self, job_id):
        """A drawing was accepted and sprayed."""
        self.used += 1
        self.jobs.append(job_id)

    def __repr__(self):
        return "window {} — {}/{} used".format(self.window, self.used, self.cap)


# --------------------------------------------------------------------------
# Check: python -m sybil.schedule
#
# Prints the timetable, then walks a whole day minute by minute and reports
# every phase change. No robot, no waiting.
# --------------------------------------------------------------------------

if __name__ == "__main__":
    schedule = Schedule()
    schedule.describe()

    print("\n--- walking a day ---")
    day = datetime(2026, 9, 7, 8, 0)
    previous = None
    state = WindowState()

    for minute in range(int(11.5 * 60)):
        now = day + timedelta(minutes=minute)
        phase = schedule.phase(now)
        window = schedule.window_number(now)

        if phase is not previous:
            left = schedule.seconds_left_in_phase(now) / 60.0
            label = "window {}".format(window) if window else "-"
            print("  {}  {:<14} {:<9} {:.0f} min".format(
                now.strftime("%H:%M"), phase.value, label, left))
            previous = phase

    print("\n--- maintenance work, 4 drawings + 10 B tiles ---")
    for mode in (DayMode.SUBSTRATE, DayMode.WATER_ONLY):
        s = Schedule(day_mode=mode)
        for plan in (Plan.FULL, Plan.SHORT):
            sprays, waters, seconds = s.maintenance_work(4, 10, plan)
            print("  {:<10} {:<6} {} sprays + {} waterings = {:.0f} min".format(
                mode.value, plan.value, sprays, waters, seconds / 60.0))

    print("\n--- plan choice, maintenance window 1 ---")
    for minutes_in, note in [(0, "at the start"), (30, "a third gone"), (60, "two thirds gone")]:
        now = datetime(2026, 9, 7, 10, 30) + timedelta(minutes=minutes_in)
        plan = schedule.plan_for(4, b_tile_count=10, now=now)
        left = schedule.seconds_left_in_phase(now) / 60.0
        print("  {}  {:<16} {:.0f} min left -> {}".format(
            now.strftime("%H:%M"), note, left, plan.value))

    print("\n--- window cap ---")
    state.sync(1)
    for i in range(6):
        if state.is_full:
            print("  visitor {} turned away — window full".format(i + 1))
        else:
            state.record("job-{}".format(i + 1))
            print("  visitor {} accepted  ({} left)".format(i + 1, state.remaining))

    changed = state.sync(2)
    print("  new window: reset={} used={}".format(changed, state.used))

    print("\n--- measured timings take over from the guesses ---")
    import tempfile
    from pathlib import Path

    scratch = Path(tempfile.mkdtemp()) / "timings.json"
    t = Timings(path=scratch)
    set_timings(t)

    spray, water = current_estimates()
    print("  before any runs:  spray {:.0f} s, water {:.0f} s  (fallback)".format(spray, water))

    for seconds in (410, 395, 402):
        t.record(SPRAY, seconds)
    for seconds in (245, 238):
        t.record(WATER, seconds)

    t.record(SPRAY, 5000)          # outlier, ignored
    t.record(SPRAY, 9, aborted=True)  # aborted, not recorded

    spray, water = current_estimates()
    print("  after real runs:  spray {:.0f} s, water {:.0f} s  (measured)".format(spray, water))
    print("  window estimate moved from {:.0f} to {:.0f} min".format(
        schedule.maintenance_work(4, 10, Plan.FULL)[2] / 60.0
        * ESTIMATED_CYCLE_S / spray,
        schedule.maintenance_work(4, 10, Plan.FULL)[2] / 60.0))

    print("\nschedule ok")
