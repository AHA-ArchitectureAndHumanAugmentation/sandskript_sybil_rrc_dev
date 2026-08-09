#!/usr/bin/env python3
"""
300_watch_and_run.py

Watches data/in and runs the pipeline directly (NOT via ZeroMQ) -- the
simplest "just make it happen" option. Shares its actual logic with
main.py / 300b_zmq_listener.py via pipeline_utils.py.

304 now runs here too (it didn't before -- that was a real divergence
bug from copy-pasted code). 304's own MODE constant still governs what
actually happens.
"""

import subprocess
import time

import pipeline_utils as pu

POLL_INTERVAL = 2.0


def main():
    print(f"Watching for new captures in: {pu.IN_DIR}")
    print("Only NEW captures from this point forward are processed.")
    print("Press Ctrl+C to stop.\n")

    seen = set(pu.IN_DIR.glob("*/path.json"))

    try:
        while True:
            time.sleep(POLL_INTERVAL)
            current = set(pu.IN_DIR.glob("*/path.json"))

            for path_json in current - seen:
                if not pu.is_file_stable(path_json):
                    continue
                seen.add(path_json)
                pu.describe_input(path_json)
                try:
                    pu.run_pipeline(path_json)
                except subprocess.CalledProcessError as error:
                    print(f"Pipeline failed for {path_json}: {error}")

    except KeyboardInterrupt:
        print("\nStopped watching.")


if __name__ == "__main__":
    main()