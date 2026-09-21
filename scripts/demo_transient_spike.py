"""
Demo transient CPU spike.

Runs 4 CPU workers for only 10 seconds.
Produces a SHORT_SPIKE, not a PERSISTENT signal.

This script is a DEMO HELPER, not part of ORION.

Run:
    python scripts/demo_transient_spike.py
"""

import multiprocessing
import time
import os


def burn(seconds: int) -> None:
    end = time.time() + seconds
    while time.time() < end:
        sum(i * i for i in range(10000))


if __name__ == "__main__":
    workers = 4
    seconds = 10

    print("=" * 60)
    print("ORION DEMO — TRANSIENT SPIKE")
    print("=" * 60)
    print(f"PID of this script: {os.getpid()}")
    print(f"Starting {workers} workers for only {seconds} seconds...")
    print()

    procs = [
        multiprocessing.Process(target=burn, args=(seconds,))
        for _ in range(workers)
    ]

    for p in procs:
        p.start()

    for p in procs:
        p.join()

    print("Spike ended.")