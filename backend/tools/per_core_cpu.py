import time
import psutil


def monitor_per_core_cpu(
    duration=10,
    interval=2
):
    """
    Monitor CPU usage for every logical CPU core
    over a period of time.
    """

    snapshots = []

    start_time = time.time()

    while time.time() - start_time < duration:

        cpu_values = psutil.cpu_percent(
            interval=1,
            percpu=True
        )

        snapshots.append({
            "timestamp": time.time(),
            "cores": [
                round(value, 2)
                for value in cpu_values
            ]
        })

        elapsed = time.time() - start_time

        if elapsed < duration:
            time.sleep(interval)

    return snapshots


def analyze_per_core_cpu(
    snapshots
):
    """
    Analyze CPU utilization per logical core.
    """

    if not snapshots:
        return {
            "status": "NO_DATA"
        }

    core_count = len(
        snapshots[0]["cores"]
    )

    core_statistics = []

    for core_index in range(core_count):

        values = [
            snapshot["cores"][core_index]
            for snapshot in snapshots
        ]

        average = (
            sum(values)
            / len(values)
        )

        maximum = max(values)

        minimum = min(values)

        core_statistics.append({

            "core": core_index,

            "average": round(
                average,
                2
            ),

            "maximum": round(
                maximum,
                2
            ),

            "minimum": round(
                minimum,
                2
            ),

            "range": round(
                maximum - minimum,
                2
            )
        })


    averages = [
        core["average"]
        for core in core_statistics
    ]

    highest_core = max(
        core_statistics,
        key=lambda item:
        item["average"]
    )

    lowest_core = min(
        core_statistics,
        key=lambda item:
        item["average"]
    )


    # Detect imbalance between cores.

    imbalance = (
        highest_core["average"]
        - lowest_core["average"]
    )


    if imbalance >= 40:

        load_distribution = "HIGHLY_IMBALANCED"

    elif imbalance >= 20:

        load_distribution = "IMBALANCED"

    else:

        load_distribution = "BALANCED"


    return {

        "status": "ANALYZED",

        "logical_cores": core_count,

        "samples": len(
            snapshots
        ),

        "cores": core_statistics,

        "highest_average_core":
            highest_core,

        "lowest_average_core":
            lowest_core,

        "load_imbalance":
            round(
                imbalance,
                2
            ),

        "load_distribution":
            load_distribution
    }