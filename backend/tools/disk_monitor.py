import time
import psutil


def get_disk_io():
    """
    Capture current system disk I/O counters.
    """

    counters = psutil.disk_io_counters()

    if counters is None:
        return {
            "read_mb": 0,
            "write_mb": 0,
            "read_mb_per_sec": 0,
            "write_mb_per_sec": 0
        }

    return {
        "read_mb": round(
            counters.read_bytes / (1024 ** 2),
            2
        ),
        "write_mb": round(
            counters.write_bytes / (1024 ** 2),
            2
        )
    }


def monitor_disk(
    duration=10,
    interval=2
):
    """
    Monitor disk throughput over time.
    """

    snapshots = []

    previous = psutil.disk_io_counters()

    if previous is None:
        return snapshots

    start_time = time.time()

    while time.time() - start_time < duration:

        time.sleep(interval)

        current = psutil.disk_io_counters()

        if current is None:
            continue

        read_delta = (
            current.read_bytes
            - previous.read_bytes
        )

        write_delta = (
            current.write_bytes
            - previous.write_bytes
        )

        read_rate = (
            read_delta
            / (1024 ** 2)
            / interval
        )

        write_rate = (
            write_delta
            / (1024 ** 2)
            / interval
        )

        snapshots.append({
            "timestamp": time.time(),
            "read_mb_per_sec": round(
                read_rate,
                2
            ),
            "write_mb_per_sec": round(
                write_rate,
                2
            )
        })

        previous = current

    return snapshots


def analyze_disk_trends(snapshots):
    """
    Analyze disk I/O behavior.
    """

    if not snapshots:
        return {
            "status": "NO_DATA"
        }

    read_values = [
        item["read_mb_per_sec"]
        for item in snapshots
    ]

    write_values = [
        item["write_mb_per_sec"]
        for item in snapshots
    ]

    return {
        "status": "ANALYZED",

        "read": {
            "minimum": round(
                min(read_values),
                2
            ),
            "maximum": round(
                max(read_values),
                2
            ),
            "average": round(
                sum(read_values)
                / len(read_values),
                2
            )
        },

        "write": {
            "minimum": round(
                min(write_values),
                2
            ),
            "maximum": round(
                max(write_values),
                2
            ),
            "average": round(
                sum(write_values)
                / len(write_values),
                2
            )
        }
    }