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

*** SAFETY NOTE ***
304's own MODE constant (top of 304_send_to_robot.py) is the ONLY gate
between a capture and an actual robot move. Neither RUN_MODE here
changes that gate -- check 304's MODE before pressing Enter.
"""

import subprocess
import sys
import threading
import time
from pathlib import Path

import zmq

import pipeline_utils as pu

RUN_MODE = "single"  # "single" or "autonomous"

BIND_ADDRESS = "tcp://127.0.0.1:5557"
CONNECT_ADDRESS = "tcp://127.0.0.1:5557"
POLL_INTERVAL = 2.0


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
                sender.send_string(str(path_json))
                print(f"[testing watcher] Sent: {path_json}")


def run_autonomous():
    context = zmq.Context()
    receiver = context.socket(zmq.PULL)
    receiver.bind(BIND_ADDRESS)

    threading.Thread(target=testing_watcher_thread, daemon=True).start()

    print("=== AUTONOMOUS MODE ===")
    print(f"Listening on {BIND_ADDRESS}")
    print(f"TESTING watcher active on {pu.IN_DIR} -- new folders there get sent automatically.")
    print("Each capture pauses for Enter before processing. Ctrl+C to stop.\n")

    try:
        while True:
            input_path = Path(receiver.recv_string())
            if not input_path.is_file():
                print(f"Received path does not exist, skipping: {input_path}")
                continue

            pu.describe_input(input_path)
            input("Press Enter to continue...")

            try:
                pu.run_pipeline(input_path)
            except subprocess.CalledProcessError as error:
                print(f"Pipeline failed for {input_path}: {error}")

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