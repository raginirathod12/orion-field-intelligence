import json
import re
import subprocess
import time


def _run_command(
    command,
    timeout=10
):
    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False
        )

        return {
            "success":
                result.returncode == 0,

            "stdout":
                result.stdout.strip(),

            "stderr":
                result.stderr.strip(),

            "returncode":
                result.returncode
        }

    except subprocess.TimeoutExpired:

        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out.",
            "returncode": -1
        }

    except Exception as error:

        return {
            "success": False,
            "stdout": "",
            "stderr": str(error),
            "returncode": -1
        }


def read_nvidia_smi():
    """
    Read NVIDIA GPU telemetry when nvidia-smi exists.
    """

    command = [
        "nvidia-smi",
        "--query-gpu=index,name,utilization.gpu,"
        "utilization.memory,memory.used,memory.total,"
        "temperature.gpu,power.draw",
        "--format=csv,noheader,nounits"
    ]

    result = _run_command(
        command,
        timeout=5
    )

    if not result["success"]:

        return None

    gpus = []

    for line in result["stdout"].splitlines():

        if not line.strip():
            continue

        parts = [
            item.strip()
            for item in line.split(",")
        ]

        if len(parts) < 8:
            continue

        def to_float(value):

            try:
                return float(value)
            except Exception:
                return None

        gpus.append({

            "index":
                parts[0],

            "name":
                parts[1],

            "gpu_utilization_percent":
                to_float(parts[2]),

            "gpu_memory_utilization_percent":
                to_float(parts[3]),

            "memory_used_mb":
                to_float(parts[4]),

            "memory_total_mb":
                to_float(parts[5]),

            "temperature_c":
                to_float(parts[6]),

            "power_w":
                to_float(parts[7])

        })

    if not gpus:
        return None

    return {
        "method":
            "nvidia-smi",

        "status":
            "AVAILABLE",

        "gpus":
            gpus
    }


def read_windows_gpu_counters():
    """
    Read Windows GPU Engine utilization counters.

    Windows creates dynamic GPU Engine counter instances,
    so ORION enumerates the real instances instead of
    constructing counter names manually.
    """

    powershell_script = (
        "(Get-Counter "
        "'\\GPU Engine(*)\\Utilization Percentage'"
        ").CounterSamples | "
        "Select-Object Path,CookedValue | "
        "ConvertTo-Json -Compress"
    )

    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        powershell_script
    ]

    result = _run_command(
        command,
        timeout=10
    )

    if not result["success"]:

        return {
            "method":
                "windows-performance-counter",

            "status":
                "UNAVAILABLE",

            "message":
                result["stderr"]
                or
                "Windows GPU Engine counters could not be read.",

            "engines":
                []
        }

    try:

        data = json.loads(
            result["stdout"]
        )

    except json.JSONDecodeError:

        return {
            "method":
                "windows-performance-counter",

            "status":
                "ERROR",

            "message":
                "Windows GPU counter output was not valid JSON.",

            "engines":
                []
        }

    if isinstance(
        data,
        dict
    ):

        data = [
            data
        ]

    engines = []

    pid_pattern = re.compile(
        r"pid_(\d+)",
        re.IGNORECASE
    )

    for item in data or []:

        path = item.get(
            "Path",
            ""
        )

        value = item.get(
            "CookedValue",
            0
        )

        try:

            utilization = float(
                value
            )

        except Exception:

            continue

        pid = None

        pid_match = pid_pattern.search(
            path
        )

        if pid_match:

            try:
                pid = int(
                    pid_match.group(1)
                )
            except ValueError:
                pid = None

        engines.append({

            "pid":
                pid,

            "utilization_percent":
                round(
                    utilization,
                    2
                ),

            "path":
                path

        })

    return {

        "method":
            "windows-performance-counter",

        "status":
            "AVAILABLE",

        "engines":
            engines

    }


def analyze_windows_gpu(
    result
):
    """
    Convert raw Windows GPU engine readings into
    useful system-level evidence.

    GPU engine percentages should not simply be summed
    and interpreted as one physical GPU percentage because
    multiple engines can operate concurrently.
    """

    engines = result.get(
        "engines",
        []
    )

    if not engines:

        return {

            "status":
                "NO_DATA",

            "message":
                "No GPU engine utilization samples were available."

        }

    positive_engines = [

        engine

        for engine in engines

        if engine.get(
            "utilization_percent",
            0
        ) > 1

    ]

    highest_engine = max(

        engines,

        key=lambda item:
            item.get(
                "utilization_percent",
                0
            )

    )

    process_gpu = {}

    for engine in positive_engines:

        pid = engine.get(
            "pid"
        )

        if pid is None:
            continue

        utilization = engine.get(
            "utilization_percent",
            0
        )

        process_gpu[pid] = (
            process_gpu.get(
                pid,
                0
            )
            +
            utilization
        )

    top_processes = [

        {
            "pid":
                pid,

            "engine_activity_score":
                round(
                    utilization,
                    2
                )
        }

        for pid, utilization
        in sorted(
            process_gpu.items(),
            key=lambda item: item[1],
            reverse=True
        )[:10]

    ]

    return {

        "status":
            "ANALYZED",

        "engine_count":
            len(engines),

        "active_engine_count":
            len(positive_engines),

        "highest_engine_utilization_percent":
            round(
                highest_engine.get(
                    "utilization_percent",
                    0
                ),
                2
            ),

        "highest_engine_path":
            highest_engine.get(
                "path"
            ),

        "top_processes":
            top_processes

    }


def collect_gpu_snapshot():
    """
    Collect one GPU snapshot.

    NVIDIA telemetry is preferred when available.
    Otherwise Windows GPU Engine counters are used.
    """

    nvidia = read_nvidia_smi()

    if nvidia:

        return {

            "method":
                "nvidia-smi",

            "status":
                "AVAILABLE",

            "data":
                nvidia

        }

    windows = read_windows_gpu_counters()

    return {

        "method":
            windows.get(
                "method"
            ),

        "status":
            windows.get(
                "status"
            ),

        "data":
            analyze_windows_gpu(
                windows
            ),

        "raw":
            windows

    }


def monitor_gpu(
    duration=6,
    interval=2
):
    """
    Monitor GPU telemetry over time.
    """

    snapshots = []

    start_time = time.time()

    while time.time() - start_time < duration:

        snapshot = collect_gpu_snapshot()

        snapshot["timestamp"] = time.time()

        snapshots.append(
            snapshot
        )

        elapsed = time.time() - start_time

        if elapsed < duration:
            time.sleep(interval)

    return snapshots


def analyze_gpu(
    snapshots
):
    """
    Fuse GPU samples into a compact diagnostic result.
    """

    if not snapshots:

        return {

            "status":
                "NO_DATA",

            "message":
                "No GPU samples were collected."

        }

    nvidia_samples = []

    windows_samples = []

    for snapshot in snapshots:

        if snapshot.get(
            "method"
        ) == "nvidia-smi":

            data = snapshot.get(
                "data",
                {}
            )

            if data.get(
                "status"
            ) == "AVAILABLE":

                nvidia_samples.append(
                    data
                )

        elif snapshot.get(
            "method"
        ) == "windows-performance-counter":

            data = snapshot.get(
                "data",
                {}
            )

            if data.get(
                "status"
            ) == "ANALYZED":

                windows_samples.append(
                    data
                )

    # ----------------------------------------------------------
    # NVIDIA
    # ----------------------------------------------------------

    if nvidia_samples:

        gpu_statistics = {}

        for sample in nvidia_samples:

            for gpu in sample.get(
                "gpus",
                []
            ):

                index = gpu.get(
                    "index"
                )

                if index not in gpu_statistics:

                    gpu_statistics[index] = {

                        "name":
                            gpu.get(
                                "name"
                            ),

                        "utilization": [],

                        "memory_utilization": [],

                        "temperature": [],

                        "memory_used": []

                    }

                stats = gpu_statistics[index]

                if gpu.get(
                    "gpu_utilization_percent"
                ) is not None:

                    stats["utilization"].append(
                        gpu[
                            "gpu_utilization_percent"
                        ]
                    )

                if gpu.get(
                    "gpu_memory_utilization_percent"
                ) is not None:

                    stats["memory_utilization"].append(
                        gpu[
                            "gpu_memory_utilization_percent"
                        ]
                    )

                if gpu.get(
                    "temperature_c"
                ) is not None:

                    stats["temperature"].append(
                        gpu[
                            "temperature_c"
                        ]
                    )

                if gpu.get(
                    "memory_used_mb"
                ) is not None:

                    stats["memory_used"].append(
                        gpu[
                            "memory_used_mb"
                        ]
                    )

        results = []

        for index, stats in gpu_statistics.items():

            def avg(values):

                if not values:
                    return None

                return round(
                    sum(values)
                    /
                    len(values),
                    2
                )

            results.append({

                "index":
                    index,

                "name":
                    stats["name"],

                "average_gpu_utilization_percent":
                    avg(
                        stats["utilization"]
                    ),

                "maximum_gpu_utilization_percent":
                    max(
                        stats["utilization"]
                    )
                    if stats["utilization"]
                    else None,

                "average_memory_utilization_percent":
                    avg(
                        stats["memory_utilization"]
                    ),

                "average_memory_used_mb":
                    avg(
                        stats["memory_used"]
                    ),

                "average_temperature_c":
                    avg(
                        stats["temperature"]
                    )

            })

        return {

            "status":
                "ANALYZED",

            "method":
                "nvidia-smi",

            "samples":
                len(nvidia_samples),

            "gpus":
                results

        }

    # ----------------------------------------------------------
    # Windows GPU Engine
    # ----------------------------------------------------------

    if windows_samples:

        highest_utilization = max(

            sample.get(
                "highest_engine_utilization_percent",
                0
            )

            for sample
            in windows_samples

        )

        active_engine_counts = [

            sample.get(
                "active_engine_count",
                0
            )

            for sample
            in windows_samples

        ]

        return {

            "status":
                "ANALYZED",

            "method":
                "windows-performance-counter",

            "samples":
                len(windows_samples),

            "maximum_engine_utilization_percent":
                round(
                    highest_utilization,
                    2
                ),

            "average_active_engine_count":
                round(
                    sum(
                        active_engine_counts
                    )
                    /
                    len(
                        active_engine_counts
                    ),
                    2
                )

        }

    # ----------------------------------------------------------
    # Nothing available
    # ----------------------------------------------------------

    return {

        "status":
            "NO_DATA",

        "message":
            (
                "No supported GPU telemetry was exposed "
                "by the current Windows/hardware configuration."
            )

    }