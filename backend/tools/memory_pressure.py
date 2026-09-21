import subprocess
import time
import psutil


def _run_powershell_counter(counter_paths):
    """
    Read Windows Performance Counters using PowerShell.

    Returns a list of numeric counter values.
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


def read_memory_pressure():
    """
    Collect memory-pressure indicators.

    This is intentionally different from simple RAM usage.

    Signals include:

    - available physical memory
    - committed memory percentage
    - paging activity
    - page reads
    - page writes

    Windows Performance Counters are preferred because they expose
    memory-pressure signals that psutil alone does not provide.
    """

    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()

    result = {
        "timestamp": time.time(),
        "available_memory_mb": round(
            virtual.available / (1024 ** 2),
            2
        ),
        "available_memory_percent": round(
            (
                virtual.available
                / virtual.total
            ) * 100,
            2
        ),
        "ram_used_percent": round(
            virtual.percent,
            2
        ),
        "swap_used_percent": round(
            swap.percent,
            2
        ),
        "swap_used_mb": round(
            swap.used / (1024 ** 2),
            2
        ),
        "committed_memory_percent": None,
        "pages_per_sec": None,
        "page_reads_per_sec": None,
        "page_writes_per_sec": None,
        "counter_method": "psutil_only"
    }

    if psutil.WINDOWS:

        counter_paths = [
            r"\Memory\% Committed Bytes In Use",
            r"\Memory\Pages/sec",
            r"\Memory\Page Reads/sec",
            r"\Memory\Page Writes/sec"
        ]

        values = _run_powershell_counter(
            counter_paths
        )

        if len(values) >= 4:

            result["committed_memory_percent"] = round(
                values[0],
                2
            )

            result["pages_per_sec"] = round(
                values[1],
                2
            )

            result["page_reads_per_sec"] = round(
                values[2],
                2
            )

            result["page_writes_per_sec"] = round(
                values[3],
                2
            )

            result["counter_method"] = "windows-performance-counter"

    return result


def monitor_memory_pressure(
    duration=10,
    interval=2
):
    """
    Monitor memory pressure over time.
    """

    snapshots = []

    start_time = time.time()

    while time.time() - start_time < duration:

        snapshot = read_memory_pressure()

        snapshots.append(snapshot)

        elapsed = time.time() - start_time

        if elapsed < duration:
            time.sleep(interval)

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


def analyze_memory_pressure(
    snapshots
):
    """
    Analyze memory-pressure behavior.

    IMPORTANT:

    RAM percentage alone does not determine memory pressure.

    ORION considers:

    - available memory
    - committed memory
    - paging
    - page reads
    - page writes
    - swap activity
    """

    if not snapshots:

        return {
            "status": "NO_DATA",
            "message": "No memory pressure samples were collected."
        }

    available_values = [
        item.get("available_memory_mb")
        for item in snapshots
    ]

    available_percent_values = [
        item.get("available_memory_percent")
        for item in snapshots
    ]

    committed_values = [
        item.get("committed_memory_percent")
        for item in snapshots
    ]

    pages_values = [
        item.get("pages_per_sec")
        for item in snapshots
    ]

    page_reads_values = [
        item.get("page_reads_per_sec")
        for item in snapshots
    ]

    page_writes_values = [
        item.get("page_writes_per_sec")
        for item in snapshots
    ]

    swap_values = [
        item.get("swap_used_percent")
        for item in snapshots
    ]

    average_available = _average(
        available_values
    )

    minimum_available = (
        min(
            value
            for value in available_values
            if value is not None
        )
        if any(
            value is not None
            for value in available_values
        )
        else None
    )

    average_available_percent = _average(
        available_percent_values
    )

    average_committed = _average(
        committed_values
    )

    maximum_committed = _maximum(
        committed_values
    )

    average_pages = _average(
        pages_values
    )

    maximum_pages = _maximum(
        pages_values
    )

    average_page_reads = _average(
        page_reads_values
    )

    maximum_page_reads = _maximum(
        page_reads_values
    )

    average_page_writes = _average(
        page_writes_values
    )

    maximum_page_writes = _maximum(
        page_writes_values
    )

    average_swap = _average(
        swap_values
    )

    pressure_score = 0
    evidence = []

    # ----------------------------------------------------------
    # AVAILABLE MEMORY
    # ----------------------------------------------------------

    if minimum_available is not None:

        if minimum_available < 500:

            pressure_score += 35

            evidence.append(
                f"Available physical memory fell below "
                f"{round(minimum_available, 2)} MB."
            )

        elif minimum_available < 1000:

            pressure_score += 20

            evidence.append(
                f"Available physical memory became relatively low "
                f"at {round(minimum_available, 2)} MB."
            )

    # ----------------------------------------------------------
    # COMMIT PRESSURE
    # ----------------------------------------------------------

    if maximum_committed is not None:

        if maximum_committed >= 95:

            pressure_score += 30

            evidence.append(
                f"Committed memory reached "
                f"{round(maximum_committed, 2)}%."
            )

        elif maximum_committed >= 85:

            pressure_score += 20

            evidence.append(
                f"Committed memory reached "
                f"{round(maximum_committed, 2)}%."
            )

    # ----------------------------------------------------------
    # PAGING
    # ----------------------------------------------------------

    if maximum_pages is not None:

        if maximum_pages >= 100:

            pressure_score += 20

            evidence.append(
                f"Paging activity reached "
                f"{round(maximum_pages, 2)} pages/sec."
            )

        elif maximum_pages >= 30:

            pressure_score += 10

            evidence.append(
                f"Paging activity reached "
                f"{round(maximum_pages, 2)} pages/sec."
            )

    # ----------------------------------------------------------
    # PAGE READS
    # ----------------------------------------------------------

    if maximum_page_reads is not None:

        if maximum_page_reads >= 20:

            pressure_score += 20

            evidence.append(
                f"Page-read activity reached "
                f"{round(maximum_page_reads, 2)} reads/sec."
            )

        elif maximum_page_reads >= 5:

            pressure_score += 10

            evidence.append(
                f"Page-read activity reached "
                f"{round(maximum_page_reads, 2)} reads/sec."
            )

    # ----------------------------------------------------------
    # PAGE WRITES
    # ----------------------------------------------------------

    if maximum_page_writes is not None:

        if maximum_page_writes >= 20:

            pressure_score += 15

            evidence.append(
                f"Page-write activity reached "
                f"{round(maximum_page_writes, 2)} writes/sec."
            )

        elif maximum_page_writes >= 5:

            pressure_score += 8

            evidence.append(
                f"Page-write activity reached "
                f"{round(maximum_page_writes, 2)} writes/sec."
            )

    # ----------------------------------------------------------
    # SWAP
    # ----------------------------------------------------------

    if average_swap is not None:

        if average_swap >= 25:

            pressure_score += 15

            evidence.append(
                f"Average swap usage was "
                f"{round(average_swap, 2)}%."
            )

    pressure_score = min(
        pressure_score,
        100
    )

    if pressure_score >= 70:

        pressure_status = "HIGH"

    elif pressure_score >= 40:

        pressure_status = "MODERATE"

    else:

        pressure_status = "LOW"

    if pressure_status == "LOW":

        evidence.insert(
            0,
            "No strong memory-pressure condition was observed."
        )

    return {
        "status": "ANALYZED",
        "samples": len(snapshots),
        "pressure_score": pressure_score,
        "pressure_status": pressure_status,
        "available_memory": {
            "average_mb": (
                round(average_available, 2)
                if average_available is not None
                else None
            ),
            "minimum_mb": (
                round(minimum_available, 2)
                if minimum_available is not None
                else None
            ),
            "average_percent": (
                round(
                    average_available_percent,
                    2
                )
                if average_available_percent is not None
                else None
            )
        },
        "commit": {
            "average_percent": (
                round(
                    average_committed,
                    2
                )
                if average_committed is not None
                else None
            ),
            "maximum_percent": (
                round(
                    maximum_committed,
                    2
                )
                if maximum_committed is not None
                else None
            )
        },
        "paging": {
            "average_pages_per_sec": (
                round(
                    average_pages,
                    2
                )
                if average_pages is not None
                else None
            ),
            "maximum_pages_per_sec": (
                round(
                    maximum_pages,
                    2
                )
                if maximum_pages is not None
                else None
            ),
            "average_page_reads_per_sec": (
                round(
                    average_page_reads,
                    2
                )
                if average_page_reads is not None
                else None
            ),
            "maximum_page_reads_per_sec": (
                round(
                    maximum_page_reads,
                    2
                )
                if maximum_page_reads is not None
                else None
            ),
            "average_page_writes_per_sec": (
                round(
                    average_page_writes,
                    2
                )
                if average_page_writes is not None
                else None
            ),
            "maximum_page_writes_per_sec": (
                round(
                    maximum_page_writes,
                    2
                )
                if maximum_page_writes is not None
                else None
            )
        },
        "swap": {
            "average_used_percent": (
                round(
                    average_swap,
                    2
                )
                if average_swap is not None
                else None
            )
        },
        "evidence": evidence,
        "interpretation": (
            "STRONG_MEMORY_PRESSURE"
            if pressure_status == "HIGH"
            else
            "POSSIBLE_MEMORY_PRESSURE"
            if pressure_status == "MODERATE"
            else
            "NO_STRONG_MEMORY_PRESSURE_OBSERVED"
        )
    }