# Messaging: Talking to Lin's Pipeline

Two independent systems — this repo, and Lin's depth-camera capture
pipeline — need to notify each other without either knowing the other's
internals. Two separate one-way channels handle this.

| Direction | Port | Sender | Receiver |
|---|---:|---|---|
| Captures in | `5557` | Lin's pipeline | This repo (`main.py`, autonomous mode) |
| Next tile out | `5558` | This repo (`tile_announcer.py`) | Lin's pipeline (`tile_reciever.py` stands in for now) |

```text
Lin's pipeline  --captures, port 5557-->  this repo
this repo       --next tile, port 5558--> Lin's pipeline
```

## 1. Why ZeroMQ, not MQTT

The original plan was MQTT with a broker. Built with ZeroMQ instead: no
broker process to run on a single machine, and the exact same code scales
to two machines later by changing one address — nothing else about the
code changes. See the "two machine" reference slides for the concrete
address changes and drop-in code for Lin's side.

## 2. Why PUSH/PULL, not PUB/SUB

PUB/SUB silently *drops* a message if no subscriber is connected at the
moment it's sent — wrong behavior for "you must not miss this." PUSH
queues messages and delivers them the moment a receiver connects, even if
that's later. Every sender/receiver pair in this repo uses PUSH/PULL.

> **The LINGER gotcha:** closing a PUSH socket has an infinite default wait
> trying to deliver any unsent message — if nothing is connected to
> receive it, closing can hang forever, silently freezing whatever called
> it. Every sender in this repo sets
> `sender.setsockopt(zmq.LINGER, 1000)` explicitly to cap that wait. Do
> this on any new sender.

## 3. Inbound: captures, port 5557

**`main.py`, `RUN_MODE = "autonomous"`** binds a PULL socket on
`tcp://127.0.0.1:5557` and loops forever: receive a message → pause for
Enter → run the pipeline → wait for the next one. This is the real
production receiver.

It also starts a background **testing-only** thread that watches `data/in`
directly and self-sends a message for any new folder that appears (e.g. a
Grasshopper export) — standing in for Lin's pipeline until it's wired up to
send for real.

| Tool | Purpose |
|---|---|
| `300b_zmq_listener.py` | Just the receive-and-process loop, no built-in testing watcher |
| `300b_zmq_publisher.py` | Sends one message, auto-picking the newest `data/in` folder if no path given |
| `300_watch_and_run.py` | A completely different mechanism: plain filesystem polling, no ZeroMQ at all |

## 4. Outbound: next tile, port 5558

After a real spray, `304_send_to_robot.py` calls `tile_selector.py` to pick
the next tile, then **`tile_announcer.py`** sends it:

```python
with TileAnnouncer() as announcer:
    announcer.announce(next_tile)
```

This connects (as the shorter-lived side) to `tcp://127.0.0.1:5558` and
sends the tile ID as a plain string. In production, Lin's pipeline should
bind a PULL socket to receive these — she is the stable, always-listening
side for this direction, the reverse of the inbound channel.

**`tile_reciever.py`** (misspelled on disk) is the stand-in for that real
receiver, for testing your own sending code before Lin has hers built:

```powershell
python tile_reciever.py
```

Always start this before anything that might announce a tile — with
`LINGER` set, a missing receiver no longer hangs forever, but the message
is still only delivered if something is listening when it's sent or
connects shortly after.

## 5. Moving to two machines

Only two addresses change:

| File | Setting | One machine | Two machines |
|---|---|---|---|
| `main.py` | `BIND_ADDRESS` | `tcp://127.0.0.1:5557` | `tcp://*:5557` |
| `tile_announcer.py` | `CONNECT_ADDRESS` | `tcp://127.0.0.1:5558` | Lin's real machine IP |

No internet connection is required for this, at any point — `tcp://` is
plain local-network TCP either way; a router or even a direct cable between
the two machines is sufficient. The one practical thing that does trip
this up on a real network: a firewall on either machine blocking the port,
even on a fully offline local network.
