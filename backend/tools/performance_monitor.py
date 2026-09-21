import time
import psutil


def take_snapshot():
    """
    Capture a real-time performance snapshot.
    """

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "timestamp": time.time(),

        "cpu_usage_percent": psutil.cpu_percent(
            interval=1
        ),

        "ram_usage_percent": memory.percent,

        "ram_used_gb": round(
            memory.used / (1024 ** 3),
            2
        ),

        "disk_free_gb": round(
            disk.free / (1024 ** 3),
            2
        )
    }


def monitor_system(
    duration=10,
    interval=2
):
    """
    Monitor system performance continuously
    for a short period.
    """

    snapshots = []

    start_time = time.time()

    while time.time() - start_time < duration:

        snapshot = take_snapshot()

        snapshots.append(snapshot)

        elapsed = time.time() - start_time

        if elapsed < duration:
            time.sleep(interval)

    return snapshots


def analyze_trends(snapshots):
    """
    Analyze CPU and RAM trends across
    collected monitoring snapshots.
    """

    if not snapshots:

        return {
            "status": "NO_DATA",
            "message": (
                "No monitoring data was collected."
            )
        }

    cpu_values = [
        snapshot["cpu_usage_percent"]
        for snapshot in snapshots
    ]

    ram_values = [
        snapshot["ram_usage_percent"]
        for snapshot in snapshots
    ]

    return {
        "status": "ANALYZED",

        "samples": len(snapshots),

        "cpu": {
            "minimum": round(
                min(cpu_values),
                2
            ),

            "maximum": round(
                max(cpu_values),
                2
            ),

            "average": round(
                sum(cpu_values) / len(cpu_values),
                2
            )
        },

        "ram": {
            "minimum": round(
                min(ram_values),
                2
            ),

            "maximum": round(
                max(ram_values),
                2
            ),

            "average": round(
                sum(ram_values) / len(ram_values),
                2
            )
        }
    }