from tools.per_core_cpu import (
    monitor_per_core_cpu,
    analyze_per_core_cpu
)

from tools.cpu_frequency import (
    monitor_cpu_frequency,
    analyze_cpu_frequency
)

from tools.temperature_monitor import (
    monitor_temperature,
    analyze_temperature
)

from tools.windows_service_inspector import (
    inspect_windows_services
)

from tools.process_deep_investigator import (
    investigate_process
)

from tools.process_temporal_profiler import (
    profile_process
)

from tools.gpu_monitor import (
    monitor_gpu,
    analyze_gpu
)

from tools.memory_pressure import (
    monitor_memory_pressure,
    analyze_memory_pressure
)

from tools.storage_latency import (
    monitor_storage_latency,
    analyze_storage_latency
)


def execute_investigation_tool(
    tool_name,
    duration=6,
    interval=2,
    target_pids=None
):
    """
    Execute one investigation tool selected
    by ORION's investigation planner.

    All currently implemented investigation tools
    are read-only.
    """

    target_pids = target_pids or []

    # ==========================================================
    # PER-CORE CPU
    # ==========================================================

    if tool_name == "per_core_cpu":

        snapshots = monitor_per_core_cpu(
            duration=duration,
            interval=interval
        )

        return {
            "tool": tool_name,
            "status": "EXECUTED",
            "data": analyze_per_core_cpu(
                snapshots
            )
        }

    # ==========================================================
    # CPU FREQUENCY
    # ==========================================================

    elif tool_name == "cpu_frequency":

        snapshots = monitor_cpu_frequency(
            duration=duration,
            interval=interval
        )

        return {
            "tool": tool_name,
            "status": "EXECUTED",
            "data": analyze_cpu_frequency(
                snapshots
            )
        }

    # ==========================================================
    # TEMPERATURE
    # ==========================================================

    elif tool_name == "temperature":

        snapshots = monitor_temperature(
            duration=duration,
            interval=interval
        )

        return {
            "tool": tool_name,
            "status": "EXECUTED",
            "data": analyze_temperature(
                snapshots
            )
        }

    # ==========================================================
    # WINDOWS SERVICES
    # ==========================================================

    elif tool_name == "windows_services":

        result = inspect_windows_services(
            target_pids=target_pids
        )

        return {
            "tool": tool_name,
            "status": result.get(
                "status",
                "ERROR"
            ),
            "target_pids": target_pids,
            "data": result
        }

    # ==========================================================
    # PROCESS DEEP INVESTIGATION
    # ==========================================================

    elif tool_name == "process_deep_investigation":

        if not target_pids:

            return {
                "tool": tool_name,
                "status": "ERROR",
                "message": (
                    "No target process PID "
                    "was provided."
                )
            }

        investigations = []

        for pid in target_pids:

            result = investigate_process(
                pid
            )

            investigations.append(
                result
            )

        return {
            "tool": tool_name,
            "status": "EXECUTED",
            "target_pids": target_pids,
            "data": investigations
        }

    # ==========================================================
    # PROCESS TEMPORAL PROFILE
    # ==========================================================

    elif tool_name == "process_temporal_profile":

        if not target_pids:

            return {
                "tool": tool_name,
                "status": "ERROR",
                "message": (
                    "No target process PID "
                    "was provided."
                )
            }

        profiles = []

        for pid in target_pids:

            result = profile_process(
                pid,
                duration=duration,
                interval=interval
            )

            profiles.append(
                result
            )

        return {
            "tool": tool_name,
            "status": "EXECUTED",
            "target_pids": target_pids,
            "data": profiles
        }

    # ==========================================================
    # GPU
    # ==========================================================

    elif tool_name == "gpu_monitor":

        snapshots = monitor_gpu(
            duration=duration,
            interval=interval
        )

        return {
            "tool": tool_name,
            "status": "EXECUTED",
            "data": analyze_gpu(
                snapshots
            ),
            "samples": len(
                snapshots
            )
        }

    # ==========================================================
    # MEMORY PRESSURE
    # ==========================================================

    elif tool_name == "memory_pressure":

        snapshots = monitor_memory_pressure(
            duration=duration,
            interval=interval
        )

        return {
            "tool": tool_name,
            "status": "EXECUTED",
            "data": analyze_memory_pressure(
                snapshots
            ),
            "samples": len(
                snapshots
            )
        }

    # ==========================================================
    # STORAGE LATENCY
    # ==========================================================

    elif tool_name == "storage_latency":

        snapshots = monitor_storage_latency(
            duration=duration,
            interval=interval
        )

        return {
            "tool": tool_name,
            "status": "EXECUTED",
            "data": analyze_storage_latency(
                snapshots
            ),
            "samples": len(
                snapshots
            )
        }

    # ==========================================================
    # UNKNOWN TOOL
    # ==========================================================

    return {
        "tool": tool_name,
        "status": "UNAVAILABLE",
        "message": (
            f"No executor is currently implemented "
            f"for {tool_name}."
        )
    }