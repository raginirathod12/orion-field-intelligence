from __future__ import annotations

"""
Standalone telemetry collector script for ORION multi-node monitoring.
"""

import argparse
import platform
import time
import uuid
import psutil
import requests

def collect(name: str) -> dict:
    return {
        "node_id": str(uuid.getnode()),
        "name": name,
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "uptime_hours": (time.time() - psutil.boot_time()) / 3600,
    }


def main():
    parser = argparse.ArgumentParser(description="Collect and report telemetry to ORION server.")
    parser.add_argument("--server", default="http://127.0.0.1:8000", help="ORION server URL")
    parser.add_argument("--interval", default=30, type=int, help="Reporting interval in seconds")
    parser.add_argument("--name", default=platform.node(), help="Node name")

    args = parser.parse_args()

    print(f"Reporting to {args.server} every {args.interval}s as {args.name}")

    while True:
        data = collect(args.name)
        try:
            response = requests.post(f"{args.server}/nodes/report", json=data, timeout=5)
            response.raise_for_status()
            print(f"  Reported: CPU={data['cpu_percent']:.0f}% RAM={data['ram_percent']:.0f}% DISK={data['disk_percent']:.0f}%")
        except requests.RequestException as error:
            print(f"  Report failed: {error}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()