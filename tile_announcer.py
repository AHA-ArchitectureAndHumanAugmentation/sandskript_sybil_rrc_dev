"""
tile_announcer.py

Sends the newly-selected tile to Lin, via ZeroMQ PUSH.

LINGER is set explicitly, not left at ZeroMQ's default of "wait
forever." Without this, if no receiver is connected when this closes,
__exit__ hangs INDEFINITELY trying to deliver the message -- silently
freezing 304 and everything upstream of it in main.py, no error shown.
LINGER_MS caps how long it'll wait before giving up and closing anyway.

*** COORDINATION NEEDED WITH LIN ***
"""

import time
import zmq

CONNECT_ADDRESS = "tcp://127.0.0.1:5558"
LINGER_MS = 1000  # max wait to deliver on close, then gives up


class TileAnnouncer:
    def __init__(self, connect_address=CONNECT_ADDRESS):
        self.connect_address = connect_address
        self.context = None
        self.sender = None

    def __enter__(self):
        self.context = zmq.Context()
        self.sender = self.context.socket(zmq.PUSH)
        self.sender.setsockopt(zmq.LINGER, LINGER_MS)
        self.sender.connect(self.connect_address)
        time.sleep(0.2)  # let the connect handshake settle before sending
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.sender is not None:
            self.sender.close()
        if self.context is not None:
            self.context.term()
        return False

    def announce(self, tile_id):
        self.sender.send_string(str(tile_id))
        print(f"Announced tile {tile_id} to {self.connect_address}")


if __name__ == "__main__":
    with TileAnnouncer() as announcer:
        announcer.announce(3)