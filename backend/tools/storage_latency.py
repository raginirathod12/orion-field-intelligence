import subprocess
import time
import psutil


def _run_powershell_counter(counter_paths):
    """
    Read Windows Performance Counters through PowerShell.
    """

    if not counter_paths:
        return []

    path_arguments = ",".join(
        f"'{path}'"
        for path in counter_paths
    )

    script = f"""
$counter = Get-Counter -Counter {path_arguments} -ErrorAction Stop
$counter.CounterSamples | ForEach-Object {{
    $_.CookedValue
}}
"""

    try:

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return []

        values = []

        for line in result.stdout.splitlines():

            line = line.strip()

            if not line:
                continue

            try:
                values.append(float(line))
            except ValueError:
                continue

        return values

    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        Exception
    ):
        return []


def read_storage_latency():
    """
    Collect storage-latency indicators.

    Primary Windows counters:

    - Avg. Disk sec/Read
    - Avg. Disk sec/Write
    - Current Disk Queue Length

    Values for latency are converted from seconds
    to milliseconds.
    """

    result = {
        "timestamp": time.time(),
        "read_latency_ms": None,
        "write_latency_ms": None,
        "disk_queue_length": None,
        "read_mb_per_sec": None,
        "write_mb_per_sec": None,
        "counter_method": "unavailable"
    }

    if not psutil.WINDOWS:
        return result

    counter_paths = [
        r"\PhysicalDisk(_Total)\Avg. Disk sec/Read",
        r"\PhysicalDisk(_Total)\Avg. Disk sec/Write",
        r"\PhysicalDisk(_Total)\Current Disk Queue Length",
        r"\PhysicalDisk(_Total)\Disk Read Bytes/sec",
        r"\PhysicalDisk(_Total)\Disk Write Bytes/sec"
    ]

    values = _run_powershell_counter(
        counter_paths
    )

    if len(values) >= 5:

        result["read_latency_ms"] = round(
            values[0] * 1000,
            3
        )

        result["write_latency_ms"] = round(
            values[1] * 1000,
            3
        )

        result["disk_queue_length"] = round(
            values[2],
            2
        )

        result["read_mb_per_sec"] = round(
            values[3] / (1024 ** 2),
            2
        )

        result["write_mb_per_sec"] = round(
            values[4] / (1024 ** 2),
            2
        )

        result["counter_method"] = (
            "windows-performance-counter"
        )

        return result

    # ----------------------------------------------------------
    # FALLBACK: psutil throughput
    # ----------------------------------------------------------

    counters = psutil.disk_io_counters()

    if counters:

        result["read_mb_per_sec"] = 0
        result["write_mb_per_sec"] = 0
        result["counter_method"] = "psutil-throughput"

    return result


def monitor_storage_latency(
    duration=10,
    interval=2
):
    """
    Monitor storage performance over time.
    """

    snapshots = []

    previous = psutil.disk_io_counters()

    start_time = time.time()

    while time.time() - start_time < duration:

        time.sleep(interval)

        current = psutil.disk_io_counters()

        snapshot = read_storage_latency()

        if (
            previous is not None
            and current is not None
        ):

            read_delta = (
                current.read_bytes
                - previous.read_bytes
            )

            write_delta = (
                current.write_bytes
                - previous.write_bytes
            )

            snapshot["psutil_read_mb_per_sec"] = round(
                read_delta
                / (1024 ** 2)
                / interval,
                2
            )

            snapshot["psutil_write_mb_per_sec"] = round(
                write_delta
                / (1024 ** 2)
                / interval,
                2
            )

        snapshots.append(
            snapshot
        )

        previous = current

    return snapshots


def _average(values):

    values = [
        value
        for value in values
        if value is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def _maximum(values):

    values = [
        value
        for value in values
        if value is not None
    ]

    if not values:
        return None

    return max(values)


def analyze_storage_latency(
    snapshots
):
    """
    Analyze storage latency and I/O activity.

    IMPORTANT:

    High throughput is not automatically a storage problem.

    ORION gives much more weight to latency and queue depth.
    """

    if not snapshots:

        return {
            "status": "NO_DATA",
            "message": "No storage samples were collected."
        }

    read_latency_values = [
        item.get("read_latency_ms")
        for item in snapshots
    ]

    write_latency_values = [
        item.get("write_latency_ms")
        for item in snapshots
    ]

    queue_values = [
        item.get("disk_queue_length")
        for item in snapshots
    ]

    read_values = []

    write_values = []

    for item in snapshots:

        read_value = (
            item.get("read_mb_per_sec")
        )

        write_value = (
            item.get("write_mb_per_sec")
        )

        if read_value is None:

            read_value = item.get(
                "psutil_read_mb_per_sec"
            )

        if write_value is None:

            write_value = item.get(
                "psutil_write_mb_per_sec"
            )

        read_values.append(
            read_value
        )

        write_values.append(
            write_value
        )

    average_read_latency = _average(
        read_latency_values
    )

    maximum_read_latency = _maximum(
        read_latency_values
    )

    average_write_latency = _average(
        write_latency_values
    )

    maximum_write_latency = _maximum(
        write_latency_values
    )

    average_queue = _average(
        queue_values
    )

    maximum_queue = _maximum(
        queue_values
    )

    average_read = _average(
        read_values
    )

    average_write = _average(
        write_values
    )

    score = 0

    evidence = []

    # ----------------------------------------------------------
    # READ LATENCY
    # ----------------------------------------------------------

    if maximum_read_latency is not None:

        if maximum_read_latency >= 100:

            score += 40

            evidence.append(
                f"Observed read latency reached "
                f"{round(maximum_read_latency, 3)} ms."
            )

        elif maximum_read_latency >= 50:

            score += 25

            evidence.append(
                f"Read latency became elevated at "
                f"{round(maximum_read_latency, 3)} ms."
            )

        elif maximum_read_latency >= 20:

            score += 10

            evidence.append(
                f"Read latency reached "
                f"{round(maximum_read_latency, 3)} ms."
            )

    # ----------------------------------------------------------
    # WRITE LATENCY
    # ----------------------------------------------------------

    if maximum_write_latency is not None:

        if maximum_write_latency >= 100:

            score += 40

            evidence.append(
                f"Observed write latency reached "
                f"{round(maximum_write_latency, 3)} ms."
            )

        elif maximum_write_latency >= 50:

            score += 25

            evidence.append(
                f"Write latency became elevated at "
                f"{round(maximum_write_latency, 3)} ms."
            )

        elif maximum_write_latency >= 20:

            score += 10

            evidence.append(
                f"Write latency reached "
                f"{round(maximum_write_latency, 3)} ms."
            )

    # ----------------------------------------------------------
    # QUEUE DEPTH
    # ----------------------------------------------------------

    if maximum_queue is not None:

        if maximum_queue >= 4:

            score += 30

            evidence.append(
                f"Disk queue depth reached "
                f"{round(maximum_queue, 2)}."
            )

        elif maximum_queue >= 2:

            score += 15

            evidence.append(
                f"Disk queue depth reached "
                f"{round(maximum_queue, 2)}."
            )

    score = min(
        score,
        100
    )

    if score >= 70:

        storage_status = "HIGH"

    elif score >= 35:

        storage_status = "MODERATE"

    else:

        storage_status = "LOW"

    if storage_status == "LOW":

        evidence.insert(
            0,
            "No strong storage-latency condition was observed."
        )

    return {
        "status": "ANALYZED",
        "samples": len(snapshots),
        "storage_pressure_score": score,
        "storage_pressure_status": storage_status,
        "latency": {
            "read_average_ms": (
                round(
                    average_read_latency,
                    3
                )
                if average_read_latency is not None
                else None
            ),
            "read_maximum_ms": (
                round(
                    maximum_read_latency,
                    3
                )
                if maximum_read_latency is not None
                else None
            ),
            "write_average_ms": (
                round(
                    average_write_latency,
                    3
                )
                if average_write_latency is not None
                else None
            ),
            "write_maximum_ms": (
                round(
                    maximum_write_latency,
                    3
                )
                if maximum_write_latency is not None
                else None
            )
        },
        "queue": {
            "average": (
                round(
                    average_queue,
                    2
                )
                if average_queue is not None
                else None
            ),
            "maximum": (
                round(
                    maximum_queue,
                    2
                )
                if maximum_queue is not None
                else None
            )
        },
        "throughput": {
            "read_average_mb_per_sec": (
                round(
                    average_read,
                    2
                )
                if average_read is not None
                else None
            ),
            "write_average_mb_per_sec": (
                round(
                    average_write,
                    2
                )
                if average_write is not None
                else None
            )
        },
        "evidence": evidence,
        "interpretation": (
            "STRONG_STORAGE_LATENCY"
            if storage_status == "HIGH"
            else
            "POSSIBLE_STORAGE_LATENCY"
            if storage_status == "MODERATE"
            else
            "NO_STRONG_STORAGE_LATENCY_OBSERVED"
        )
    }