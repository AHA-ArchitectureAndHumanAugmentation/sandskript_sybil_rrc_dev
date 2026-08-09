"""
tile_announcer.py

Sends the newly-selected tile to Lin, via ZeroMQ PUSH -- the
"Charlotte -> Lin" direction, mirroring 300b's "Lin -> Charlotte"
listener/publisher pair but going the other way.

Payload: just the tile ID, as a plain string -- per the plan, "the
only message that gets sent is which tile is selected."

Port 5558 -- deliberately different from 5557 (Charlotte's INBOUND
port for receiving captures from Lin). Two separate channels, one
each direction.

*** COORDINATION NEEDED WITH LIN ***
Assumes her side will eventually BIND a PULL socket to receive these
(the stable side), while this file CONNECTs and sends (the transient
side) -- same convention as 300b_zmq_listener.py. The real address
still needs confirming with her; tile_announcer_test_receiver.py lets
you test this side without her code existing yet.
"""

import zmq

# TODO: confirm the real address with Lin once her receiver exists.
CONNECT_ADDRESS = "tcp://127.0.0.1:5558"


class TileAnnouncer:
    def __init__(self, connect_address=CONNECT_ADDRESS):
        self.connect_address = connect_address
        self.context = None
        self.sender = None

    def __enter__(self):
        self.context = zmq.Context()
        self.sender = self.context.socket(zmq.PUSH)
        self.sender.connect(self.connect_address)
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
    import time
    with TileAnnouncer() as announcer:
        time.sleep(0.5)  # let the connect handshake settle
        announcer.announce(3)