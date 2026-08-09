#!/usr/bin/env python3
"""
tile_receiver.py

Receives tile announcements sent by tile_announcer.py. Right now this
is a STAND-IN for Lin's real receiver, which doesn't exist yet on her
side -- lets you confirm the sending side works correctly without her
code built. Once she has her own receiver, this either gets replaced
by hers or kept as a local dev/testing tool -- your call at that point.

Usage:
    python tile_receiver.py
"""

import zmq

BIND_ADDRESS = "tcp://127.0.0.1:5558"


def main():
    context = zmq.Context()
    receiver = context.socket(zmq.PULL)
    receiver.bind(BIND_ADDRESS)

    print(f"Listening for tile announcements on {BIND_ADDRESS}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            tile_id = receiver.recv_string()
            print(f"Received tile announcement: tile {tile_id}")
    except KeyboardInterrupt:
        print("\nStopped listening.")
    finally:
        receiver.close()
        context.term()


if __name__ == "__main__":
    main()