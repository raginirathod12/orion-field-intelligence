"""
Demo memory load generator.

Allocates 4 GB of RAM and holds it for 120 seconds.

This script is a DEMO HELPER, not part of ORION.

Run:
    python scripts/demo_memory_load.py

Press CTRL+C to stop early.
"""

import time
import os


if __name__ == "__main__":
    chunk_size = 100 * 1024 * 1024   # 100 MB per chunk
    chunks = 40                       # 40 chunks = 4 GB

    print("=" * 60)
    print("ORION DEMO — MEMORY LOAD GENERATOR")
    print("=" * 60)
    print(f"PID of this script: {os.getpid()}")
    print(f"Allocating {chunks * 100} MB of RAM...")
    print()

    blocks = []

    try:
        for i in range(chunks):
            # Allocate 100 MB
            blocks.append(bytearray(chunk_size))
            print(f"  Allocated {(i + 1) * 100} MB")
            time.sleep(0.5)

        print()
        print("Holding memory for 120 seconds...")
        print("Press CTRL+C to stop early.")
        print()

        time.sleep(120)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        blocks.clear()
        print("Memory released.")