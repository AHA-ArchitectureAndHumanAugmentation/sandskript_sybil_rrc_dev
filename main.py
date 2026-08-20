#!/usr/bin/env python3
"""Runs the toolpath pipeline: convert -> process -> send to robot.

Actual pipeline logic lives in pipeline_utils.py, shared with
300_watch_and_run.py, 300b_zmq_listener.py, and 300b_test_publisher.py.
This file is just the two entry-point modes.

RUN_MODE:
    "single"     (default) -- process ONE capture and exit. Auto-picks
                                the newest timestamped folder in data/in,
                                or pass a path as an argument. Waits for
                                a keypress before starting.
    "autonomous" -- runs forever: receives ZeroMQ messages, pauses for
                                Enter, then processes. ALSO runs a
                                background TESTING thread that sends a
                                message for each new data/in folder,
                                standing in for Lin's real pipeline.

TILE ANNOUNCING (autonomous mode only):
    Before listening, and after each pipeline run, this announces a tile
    to the tracking app over ZeroMQ (via TileAnnouncer) -- otherwise
    tracking has no tile to work on and just waits forever.

    START_TILE_ID   -- tile to announce first.
    AUTO_SELECT_TILE -- True: use tile_selector.py after the first tile.
                        False: keep re-announcing START_TILE_ID.

*** SAFETY NOTE ***
304's own MODE constant (top of 304_send_to_robot.py) is the ONLY gate
between a capture and an actual robot move. Neither RUN_MODE here
changes that gate -- check 304's MODE before pressing Enter.
"""

from email.mime import message
import subprocess
import sys
import threading
import time
from pathlib import Path

import zmq

import pipeline_utils as pu
from tile_announcer import TileAnnouncer
from tile_selector import TileSelector

RUN_MODE = "autonomous"  # "single" or "autonomous"

BIND_ADDRESS = "tcp://127.0.0.1:5557"
CONNECT_ADDRESS = "tcp://127.0.0.1:5558"
POLL_INTERVAL = 2.0

ENABLE_TESTING_WATCHER = False  # True = also self-send GH exports for testing; False = only real ZeroMQ senders (Lin)

START_TILE_ID = 3       # tile announced first
AUTO_SELECT_TILE = False  # True = tile_selector picks after that; False = keep resending START_TILE_ID


def run_single():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else pu.latest_input_path()
    pu.describe_input(input_path)
    input("Press Enter to continue...")
    pu.run_pipeline(input_path)


def testing_watcher_thread():
    """TESTING ONLY -- sends a ZeroMQ message for each new data/in
    folder, standing in for Lin's real pipeline."""
    context = zmq.Context()
    sender = context.socket(zmq.PUSH)
    sender.connect(CONNECT_ADDRESS)
    time.sleep(0.5)

    seen = set(p for p in pu.IN_DIR.iterdir() if p.is_dir() and pu.TIMESTAMP_FOLDER.match(p.name))

    while True:
        time.sleep(POLL_INTERVAL)
        current = set(p for p in pu.IN_DIR.iterdir() if p.is_dir() and pu.TIMESTAMP_FOLDER.match(p.name))
        for folder in current - seen:
            seen.add(folder)
            path_json = folder / "path.json"
            if pu.is_file_stable(path_json):
                sender.send_string(path_json.read_text(encoding="utf-8"))
                print(f"[testing watcher] Sent: {path_json}")


def announce_tile(tile_id):
    """Sends a specific tile_id, no selector logic."""
    with TileAnnouncer() as announcer:
        announcer.announce(tile_id)
    return tile_id


def announce_next_tile():
    """Used for every round AFTER the first. Selector picks if
    AUTO_SELECT_TILE, else keeps resending START_TILE_ID."""
    if AUTO_SELECT_TILE:
        tile_id = TileSelector().select()
    else:
        tile_id = START_TILE_ID
    return announce_tile(tile_id)


def run_autonomous():
    context = zmq.Context()
    receiver = context.socket(zmq.PULL)
    receiver.bind(BIND_ADDRESS)

    if ENABLE_TESTING_WATCHER:
        threading.Thread(target=testing_watcher_thread, daemon=True).start()

    print("=== AUTONOMOUS MODE ===")
    print(f"Listening on {BIND_ADDRESS}")
    if ENABLE_TESTING_WATCHER:
        print(f"TESTING watcher active on {pu.IN_DIR} -- new folders there get sent automatically.")
    print("Each capture pauses for Enter before processing. Ctrl+C to stop.\n")

    tile_id = announce_tile(START_TILE_ID)  # first round always uses START_TILE_ID
    print(f"Announced starting tile: {tile_id} (AUTO_SELECT_TILE={AUTO_SELECT_TILE})\n")

    try:
        while True:
            message = receiver.recv_string()
            input_path = pu.save_received_capture(message)
            if not input_path.is_file():
                print(f"Received path does not exist, skipping: {input_path}")
                continue

            pu.describe_input(input_path)
            input("Press Enter to continue...")

            try:
                pu.run_pipeline(input_path)
            except subprocess.CalledProcessError as error:
                print(f"Pipeline failed for {input_path}: {error}")

            tile_id = announce_next_tile()
            print(f"Announced next tile: {tile_id} (AUTO_SELECT_TILE={AUTO_SELECT_TILE})")
            print("Waiting for next capture...\n")

    except KeyboardInterrupt:
        print("\nStopped listening.")
    finally:
        receiver.close()
        context.term()


if __name__ == "__main__":
    if RUN_MODE == "single":
        run_single()
    elif RUN_MODE == "autonomous":
        run_autonomous()
    else:
        raise ValueError(f"Unknown RUN_MODE: {RUN_MODE!r} -- use 'single' or 'autonomous'.")