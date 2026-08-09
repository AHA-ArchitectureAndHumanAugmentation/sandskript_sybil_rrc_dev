#!/usr/bin/env python3
r"""
300b_zmq_publisher.py

STANDALONE TEST TOOL -- sends one ZeroMQ PUSH message to
300b_zmq_listener.py (or main.py in autonomous mode), simulating what
Lin's real pipeline will eventually send. Not part of the numbered
pipeline itself -- run by hand for testing only.

Usage:
    python 300b_zmq_publisher.py
    python 300b_zmq_publisher.py data\in\2026-08-07_13-04-06\path.json
"""

import sys
import time
from pathlib import Path

import zmq

import pipeline_utils as pu

CONNECT_ADDRESS = "tcp://127.0.0.1:5557"


def main():
    if len(sys.argv) > 1:
        path_json = Path(sys.argv[1])
    else:
        path_json = pu.latest_input_path()
        print(f"No path given -- auto-picked latest: {path_json}")

    if not path_json.is_file():
        raise FileNotFoundError(f"Not found: {path_json}")

    context = zmq.Context()
    sender = context.socket(zmq.PUSH)
    sender.connect(CONNECT_ADDRESS)
    time.sleep(0.5)

    sender.send_string(str(path_json))
    print(f"Sent: {path_json}")

    sender.close()
    context.term()


if __name__ == "__main__":
    main()