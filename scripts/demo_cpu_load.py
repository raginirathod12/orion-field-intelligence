"""
Demo CPU load generator.

Uses THREADS inside a SINGLE process so ORION sees one
clear, persistent, high-CPU process to investigate.

Run:
    python scripts/demo_cpu_load.py
"""

import os
import threading
import time


BURN_WORKERS = 6          # threads inside this one process
DURATION = 600            # 10 minutes — long enough for demo


def burn(seconds: int) -> None:
    end = time.time() + seconds
    while time.time() < end:
        # Tight loop, no sleep
        sum(i * i for i in range(100000))


def main() -> None:
    print("=" * 60)
    print("ORION DEMO — CPU LOAD GENERATOR (threaded)")
    print("=" * 60)
    print(f"PID of this process: {os.getpid()}")
    print(f"Starting {BURN_WORKERS} threads for {DURATION}s...")
    print()
    print("This process will use significant CPU.")
    print("ORION will see ONE high-CPU process.")
    print("Press CTRL+C to stop.")
    print()

    threads = [
        threading.Thread(target=burn, args=(DURATION,), daemon=True)
        for _ in range(BURN_WORKERS)
    ]

    for t in threads:
        t.start()

    # Also burn in the main thread so the process CPU is definitely high
    try:
        burn(DURATION)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()