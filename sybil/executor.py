"""
Sybil — robot execution.

The robot code from 304, in a form that can be called many times on one
connection. 304 uses it for a single path; the exhibition uses it for a
whole day.

The important split:

    setup()             connect, prepare, home        — once per session
    execute(toolpath)   spray one path, return home   — called many times

Previously these were one block, so every path opened and closed its own
ROS connection. Over an exhibition day that is 64 connections. Now the
connection is opened once in the morning and held.

Two interchangeable session classes:

    RobotSession      talks to the real GoFa via compas_rrc
    PreviewSession    prints what it would do and sleeps for roughly as
                      long as the motion would take. No ROS, no robot.

Both expose the same methods, so nothing above them needs to know which
one it is holding.

Lives in the RRC repo only:
    sandskript_sybil_rrc_dev/sybil/executor.py
"""

from __future__ import annotations

import time

from sybil import config


# ==========================================================================
# SETTINGS
# ==========================================================================

# --- Preview -------------------------------------------------------------
PREVIEW_TIME_SCALE = 1.0    # 1.0 = real time. 0.05 = 20x faster.
                            # Use a small value to run a whole day quickly.

# --- Robot ---------------------------------------------------------------
ACCELERATION = 20           # % of maximum
ACCELERATION_RAMP = 20      # % of maximum

TRAVEL_ZONE_MM = 10         # corner rounding between toolpath points.
                            # 0 = stop at every point (slow, exact).
                            # Larger = smoother and faster, less exact.

# --- Output --------------------------------------------------------------
VERBOSE = True              # False = only warnings and errors.
                            # Set False for the exhibition so the log stays
                            # readable across an 8 hour day.

# ==========================================================================

# compas_rrc is only needed for real robot runs. Importing it lazily means
# PreviewSession works on a machine that has no ROS and no compas_rrc.
try:
    import compas_rrc as rrc
    RRC_AVAILABLE = True
except ImportError:
    rrc = None
    RRC_AVAILABLE = False


class RobotError(RuntimeError):
    pass


def _say(*parts):
    """Print, unless VERBOSE is off."""
    if VERBOSE:
        print(*parts, flush=True)


def _travel_zone():
    """TRAVEL_ZONE_MM as a compas_rrc Zone. Falls back to the nearest
    available value, so an odd number here cannot crash a run."""
    if TRAVEL_ZONE_MM <= 0:
        return rrc.Zone.FINE
    for size in (200, 150, 100, 80, 60, 50, 40, 30, 20, 15, 10, 5, 1):
        if TRAVEL_ZONE_MM >= size:
            return getattr(rrc.Zone, "Z{}".format(size))
    return rrc.Zone.FINE


# --------------------------------------------------------------------------
# Real robot
# --------------------------------------------------------------------------

class RobotSession:
    """A live connection to the GoFa. Use as a context manager:

        with RobotSession() as robot:
            robot.prepare()
            robot.move_to_home()
    """

    is_preview = False

    def __init__(self):
        self.ros = None
        self.abb = None

    def __enter__(self):
        if not RRC_AVAILABLE:
            raise RobotError(
                "compas_rrc is not installed in this environment. "
                "Use PreviewSession, or activate the compas_rrc env."
            )
        print("\nConnecting to ROS...")
        self.ros = rrc.RosClient()
        self.ros.run()
        self.abb = rrc.AbbClient(self.ros, "/rob1")
        print("Connected to ROS.")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.ros is not None:
            try:
                if self.ros.is_connected:
                    self.ros.close()
                    print("\nROS connection closed.")
            except Exception as error:
                print("Could not close ROS:", error)
        return False

    # -- setup ------------------------------------------------------------

    def prepare(self):
        self.abb.send_and_wait(rrc.SetTool(config.TOOL_NAME))
        self.abb.send_and_wait(rrc.SetWorkObject(config.WORK_OBJECT))
        self.abb.send_and_wait(rrc.SetAcceleration(ACCELERATION, ACCELERATION_RAMP))

    def say(self, text):
        self.abb.send_and_wait(rrc.PrintText(text))

    # -- motion -----------------------------------------------------------

    def move_to_home(self):
        self.say("Moving to home configuration")
        self.abb.send_and_wait(
            rrc.MoveToJoints(config.HOME_CONFIG, [], speed=config.HOME_SPEED, zone=rrc.Zone.FINE)
        )

    def move_to_frame(self, frame, speed, description):
        _say("\nMoving to", description)
        self.abb.send_and_wait(rrc.MoveToFrame(frame, speed=speed, zone=rrc.Zone.FINE))
        _say(description, "completed.")

    def follow_frames(self, frames, speed):
        """Sends frames as one linear move. Only the last frame is waited on,
        so the robot does not stop between points."""
        travel_zone = _travel_zone()
        total = len(frames)
        for index, frame in enumerate(frames, start=1):
            is_last = index == total
            zone = rrc.Zone.FINE if is_last else travel_zone
            command = rrc.MoveToFrame(frame, speed=speed, zone=zone, motion_type=rrc.Motion.LINEAR)
            if is_last:
                self.abb.send_and_wait(command)
            else:
                self.abb.send(command)

    # -- reading ----------------------------------------------------------

    def get_joints(self):
        return self.abb.send_and_wait(rrc.GetJoints())

    def get_frame(self):
        return self.abb.send_and_wait(rrc.GetFrame())

    # -- outputs ----------------------------------------------------------

    def pump_on(self):
        _say("\nPump ON.")
        self.abb.send_and_wait(rrc.SetDigital(config.PUMP_OUTPUT, 1))

    def pump_off(self):
        _say("\nPump OFF.")
        self.abb.send_and_wait(rrc.SetDigital(config.PUMP_OUTPUT, 0))

    def spray_on(self):
        _say("\nSpray valve ON.")
        self.abb.send_and_wait(rrc.SetDigital(config.SPRAY_OUTPUT, 1))

    def spray_off(self):
        _say("\nSpray valve OFF.")
        self.abb.send_and_wait(rrc.SetDigital(config.SPRAY_OUTPUT, 0))

    def wait(self, seconds):
        self.abb.send_and_wait(rrc.WaitTime(seconds))


# --------------------------------------------------------------------------
# Preview — no robot
# --------------------------------------------------------------------------

class PreviewSession:
    """Same methods as RobotSession, but prints instead of moving.

    Sleeps for roughly how long each motion would take, so a simulated
    exhibition day takes a believable amount of time rather than finishing
    instantly. Speed is controlled by PREVIEW_TIME_SCALE at the top of this
    file, or per instance: PreviewSession(time_scale=0.05).
    """

    is_preview = True

    def __init__(self, time_scale=None):
        self.time_scale = PREVIEW_TIME_SCALE if time_scale is None else time_scale
        self.last_frame = None

    def __enter__(self):
        print("\n=== PREVIEW SESSION — no robot connection will be made ===")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        print("\n=== PREVIEW SESSION ended ===")
        return False

    def _log(self, action, detail=""):
        _say("  [preview] {:<16} {}".format(action, detail))

    def _sleep(self, seconds):
        time.sleep(max(0.0, seconds * self.time_scale))

    # -- setup ------------------------------------------------------------

    def prepare(self):
        self._log("prepare", "tool={} wobj={}".format(config.TOOL_NAME, config.WORK_OBJECT))

    def say(self, text):
        self._log("print", text)

    # -- motion -----------------------------------------------------------

    def move_to_home(self):
        self._log("move_to_home", str(config.HOME_CONFIG))
        self._sleep(3.0)
        self.last_frame = None

    def move_to_frame(self, frame, speed, description):
        self._log("move_to_frame", "{} @ {} mm/s".format(description, speed))
        self._sleep(2.0)
        self.last_frame = frame

    def follow_frames(self, frames, speed):
        length = _path_length(frames)
        duration = length / float(speed) if speed else 0.0
        self._log(
            "follow_frames",
            "{} frames, {:.0f} mm @ {} mm/s -> {:.1f} s".format(len(frames), length, speed, duration),
        )
        self._sleep(duration)
        if frames:
            self.last_frame = frames[-1]

    # -- reading ----------------------------------------------------------

    def get_joints(self):
        return config.HOME_CONFIG, []

    def get_frame(self):
        return self.last_frame

    # -- outputs ----------------------------------------------------------

    def pump_on(self):
        self._log("pump", "ON")

    def pump_off(self):
        self._log("pump", "OFF")

    def spray_on(self):
        self._log("spray", "ON")

    def spray_off(self):
        self._log("spray", "OFF")

    def wait(self, seconds):
        self._log("wait", "{:.1f} s".format(seconds))
        self._sleep(seconds)


def _path_length(frames):
    """Total travel along a list of frames, in mm."""
    total = 0.0
    for a, b in zip(frames, frames[1:]):
        total += a.point.distance_to_point(b.point)
    return total


# --------------------------------------------------------------------------
# Executor
# --------------------------------------------------------------------------

class ToolpathExecutor:
    """Runs toolpaths on a session.

    Typical exhibition use:

        with RobotSession() as robot:
            executor = ToolpathExecutor(robot)
            executor.setup()
            for toolpath in the_whole_day:
                executor.execute(toolpath)
    """

    def __init__(self, session):
        self.session = session
        self.is_ready = False

    # -- once per session -------------------------------------------------

    def setup(self):
        """Connect-side preparation: tool, work object, acceleration, home.

        Safe to call more than once; it does nothing after the first time.
        """
        if self.is_ready:
            return

        self.session.say("Python connected to ABB")
        joints, external_axes = self.session.get_joints()
        _say("\nCurrent robot joints:", joints)

        self.session.prepare()
        self.session.move_to_home()

        self.is_ready = True
        print("\nSetup complete. Robot is at HOME.")

    # -- once per toolpath ------------------------------------------------

    def execute(self, toolpath, spray=True):
        """Sprays one toolpath and returns home.

        toolpath  an object with a .frames list and .safe_frame()
        spray     False runs the whole motion with pump and valve closed.
                  Used on water-only days and for dry testing: the timing
                  and the movement stay identical, no material comes out.

        Returns how long the whole thing took, in seconds.
        """
        if not self.is_ready:
            raise RobotError("Call setup() before execute().")

        started = time.time()

        safe_first = toolpath.safe_frame(toolpath.first)
        safe_last = toolpath.safe_frame(toolpath.last)

        self.session.say("Moving to safe frame")
        self.session.move_to_frame(safe_first, config.APPROACH_SPEED, "safe frame")
        self.session.move_to_frame(toolpath.first, config.APPROACH_SPEED, "first frame")

        pump_started = False
        spray_started = False

        try:
            if spray:
                self.session.pump_on()
                pump_started = True
                self.session.wait(config.PUMP_START_DELAY)
                self.session.spray_on()
                spray_started = True
            else:
                _say("\nspray=False — running the motion dry.")

            self.session.say("Following toolpath")
            self.session.follow_frames(toolpath.remaining, config.TOOLPATH_SPEED)

        finally:
            # Always close the outputs, even if the move failed part way.
            if spray_started:
                try:
                    self.session.spray_off()
                except Exception as error:
                    print("Could not turn spray OFF:", error, flush=True)
            if pump_started:
                try:
                    self.session.pump_off()
                except Exception as error:
                    print("Could not turn pump OFF:", error, flush=True)

        self.session.say("Retracting")
        self.session.move_to_frame(safe_last, config.APPROACH_SPEED, "final safe frame")
        self.session.move_to_home()

        duration = time.time() - started
        print("\nToolpath complete in {:.1f} s.".format(duration), flush=True)
        return duration


# --------------------------------------------------------------------------
# Check: python sybil/executor.py
#
# Runs a fake toolpath through PreviewSession. No robot, no ROS.
# --------------------------------------------------------------------------

if __name__ == "__main__":
    from compas.geometry import Frame, Point

    class _FakeToolpath:
        def __init__(self, frames):
            self.frames = frames

        @property
        def first(self):
            return self.frames[0]

        @property
        def last(self):
            return self.frames[-1]

        @property
        def remaining(self):
            return self.frames[1:]

        def safe_frame(self, frame):
            return frame

    frames = [Frame(Point(x, 0, 800), [1, 0, 0], [0, 1, 0]) for x in range(0, 1600, 100)]
    toolpath = _FakeToolpath(frames)

    with PreviewSession(time_scale=0.05) as session:
        executor = ToolpathExecutor(session)
        executor.setup()
        print("\n--- toolpath 1, spraying ---")
        executor.execute(toolpath)
        print("\n--- toolpath 2, dry run ---")
        executor.execute(toolpath, spray=False)

    print("\nexecutor ok — two toolpaths on one session")
