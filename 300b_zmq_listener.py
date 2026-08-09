#!/usr/bin/env python3
"""
300b_zmq_listener.py

Listens for ZeroMQ PUSH messages and runs the pipeline via
pipeline_utils.run_pipeline() on each one. See main.py's "autonomous"
mode for the same mechanism with a built-in testing watcher.

PUSH/PULL, not PUB/SUB: PUSH queues messages even if this listener
isn't running yet, delivering them once it connects. PUB/SUB would
silently drop a message sent before a subscriber connects.
"""

import subprocess
from pathlib import Path

import zmq

import pipeline_utils as pu

BIND_ADDRESS = "tcp://127.0.0.1:5557"


def main():
    context = zmq.Context()
    receiver = context.socket(zmq.PULL)
    receiver.bind(BIND_ADDRESS)

    print(f"Listening on {BIND_ADDRESS}")
    print("Waiting for new captures. Press Ctrl+C to stop.\n")

    try:
        while True:
            input_path = Path(receiver.recv_string())
            if not input_path.is_file():
                print(f"Received path does not exist, skipping: {input_path}")
                continue

            pu.describe_input(input_path)
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
    main()